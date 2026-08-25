from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.orchestrator.contracts import (
    RunRecord,
    TargetState,
)
from knowledge_compiler.orchestrator.queue import QueueError, RunQueue
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_state_store import FixedClock, run, target  # noqa: E402


def evidence_ready_run() -> RunRecord:
    ready = (
        target()
        .transition(TargetState.EVIDENCE_READY)
    )
    return run().with_target(ready)


def queue(tmp_path: Path, clock: FixedClock | None = None) -> RunQueue:
    clock = clock or FixedClock()
    return RunQueue(
        store_root=tmp_path / ".knowledge/state/runs",
        run=evidence_ready_run(),
        clock=clock,
    )


def test_lease_grant_is_exclusive_and_operation_scoped(tmp_path: Path) -> None:
    clock = FixedClock()
    queue_ = RunQueue(
        store_root=tmp_path / ".knowledge/state/runs", run=evidence_ready_run(), clock=clock
    )
    lease = queue_.grant_extraction_lease("module.shop.checkout", ttl=60)
    assert lease.operation == "extract"
    assert lease.attempt == 1

    with pytest.raises(QueueError, match="leased"):
        queue_.grant_extraction_lease("module.shop.checkout", ttl=60)
    with pytest.raises(QueueError, match="leased"):
        queue_.grant_verification_lease("module.shop.checkout", ttl=60)


def test_expired_lease_returns_to_queue(tmp_path: Path) -> None:
    clock = FixedClock()
    queue_ = RunQueue(
        store_root=tmp_path / ".knowledge/state/runs", run=evidence_ready_run(), clock=clock
    )
    queue_.grant_extraction_lease("module.shop.checkout", ttl=60)
    clock.now += 61
    record = queue_.expire_leases()
    target_record = queue_.target("module.shop.checkout")
    assert target_record.state is TargetState.EVIDENCE_READY
    assert target_record.lease is None
    assert record is not None


def test_stale_token_submission_rejected(tmp_path: Path) -> None:
    queue_ = queue(tmp_path)
    lease = queue_.grant_extraction_lease("module.shop.checkout", ttl=60)
    with pytest.raises(QueueError, match="lease"):
        queue_.submit_draft(
            target_id="module.shop.checkout",
            lease_token="wrong-token",
            draft_digest="sha256:" + "3" * 64,
        )
    with pytest.raises(QueueError, match="target"):
        queue_.submit_draft(
            target_id="module.shop.ghost",
            lease_token=lease.token,
            draft_digest="sha256:" + "3" * 64,
        )


def test_idempotent_replay_returns_recorded_result(tmp_path: Path) -> None:
    queue_ = queue(tmp_path)
    queue_.grant_extraction_lease("module.shop.checkout", ttl=60)
    first = queue_.submit_draft(
        target_id="module.shop.checkout",
        lease_token=queue_.target("module.shop.checkout").lease.token,
        draft_digest="sha256:" + "3" * 64,
    )
    assert first.result_digest == "sha256:" + "3" * 64
    # replay with the same idempotency key and digest: no new attempt work
    replay = queue_.replay_extraction(
        target_id="module.shop.checkout",
        draft_digest="sha256:" + "3" * 64,
    )
    assert replay.result_digest == first.result_digest
    with pytest.raises(QueueError, match="payload"):
        queue_.replay_extraction(
            target_id="module.shop.checkout",
            draft_digest="sha256:" + "4" * 64,
        )


def test_wrong_operation_domain_rejected(tmp_path: Path) -> None:
    # A queued target cannot take a verification lease at all.
    queue_ = RunQueue(
        store_root=tmp_path / ".knowledge/state/runs",
        run=run(),
        clock=FixedClock(),
    )
    with pytest.raises(QueueError, match="state"):
        queue_.grant_verification_lease("module.shop.checkout", ttl=60)
