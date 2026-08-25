from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_compiler.orchestrator.contracts import (
    Lease,
    RunRecord,
    TargetRecord,
    TargetState,
    TerminalResult,
)


def test_target_record_persists_planner_topic_and_evidence_seeds() -> None:
    target = TargetRecord.model_validate(
        {
            "target_id": "architecture.shop.platform",
            "object_type": "architecture",
            "topic": "Shop platform boundaries",
            "evidence_seeds": ("checkout", "inventory"),
            "state": "queued",
            "attempt": 1,
            "repair_attempts": 0,
            "required": True,
            "priority": 1,
            "result": None,
            "published_object_id": None,
            "request_digest": "sha256:" + "1" * 64,
            "result_digest": None,
            "diagnostics": (),
            "lease": None,
        }
    )

    assert target.topic == "Shop platform boundaries"
    assert target.evidence_seeds == ("checkout", "inventory")


class FixedClock:
    def __init__(self) -> None:
        self.now = 1_000_000

    def __call__(self) -> int:
        return self.now


def target(state: TargetState = TargetState.QUEUED, **overrides: object) -> TargetRecord:
    values: dict[str, object] = {
        "target_id": "module.shop.checkout",
        "object_type": "module",
        "state": state,
        "attempt": 1,
        "repair_attempts": 0,
        "required": True,
        "priority": 1,
        "result": None,
        "published_object_id": None,
        "request_digest": "sha256:" + "1" * 64,
        "result_digest": None,
        "diagnostics": (),
        "lease": None,
    }
    values.update(overrides)
    return TargetRecord.model_validate(values)


def run(**overrides: object) -> RunRecord:
    values: dict[str, object] = {
        "run_id": "run-001",
        "repository_id": "fixture/probe-shop",
        "snapshot_id": "sha256:" + "2" * 64,
        "executor": "llm",
        "active": True,
        "targets": (target(),),
    }
    values.update(overrides)
    return RunRecord.model_validate(values)


def test_legal_pipeline_transitions() -> None:
    record = target()
    for next_state in (
        TargetState.EVIDENCE_READY,
        TargetState.EXTRACTION_LEASED,
        TargetState.DRAFT_SUBMITTED,
        TargetState.STRUCTURAL_VALIDATED,
        TargetState.SEMANTIC_PENDING,
        TargetState.VERIFICATION_LEASED,
        TargetState.VERIFIED,
    ):
        record = record.transition(next_state)
    assert record.state is TargetState.VERIFIED


@pytest.mark.parametrize(
    "jump",
    [
        TargetState.DRAFT_SUBMITTED,
        TargetState.STRUCTURAL_VALIDATED,
        TargetState.VERIFIED,
    ],
)
def test_illegal_transition_skipping_states_rejected(jump: TargetState) -> None:
    with pytest.raises(ValueError, match="transition"):
        target().transition(jump)


def test_repair_pending_loops_back_to_extraction() -> None:
    leased = target().transition(TargetState.EVIDENCE_READY).transition(
        TargetState.EXTRACTION_LEASED
    )
    repaired = leased.transition(TargetState.REPAIR_PENDING)
    again = repaired.transition(TargetState.EXTRACTION_LEASED)
    assert again.repair_attempts == 1


def test_repair_attempts_bounded() -> None:
    record = target().transition(TargetState.EVIDENCE_READY)
    for _ in range(3):
        record = record.transition(TargetState.EXTRACTION_LEASED)
        record = record.transition(TargetState.REPAIR_PENDING)
    with pytest.raises(ValueError, match="repair"):
        record.transition(TargetState.EXTRACTION_LEASED)


@pytest.mark.parametrize(
    "result",
    [
        TerminalResult.INVALID,
        TerminalResult.CONFLICTED,
        TerminalResult.INSUFFICIENT_EVIDENCE,
        TerminalResult.RETIRED,
        TerminalResult.SKIPPED,
    ],
)
def test_terminal_results_are_absorbing(result: TerminalResult) -> None:
    finished = target().finish(result, diagnostics=("done-for", str(result)))
    assert finished.state is TargetState.DONE
    assert finished.result is result
    with pytest.raises(ValueError, match="terminal"):
        finished.transition(TargetState.EVIDENCE_READY)


def test_lease_carries_identity_and_expiry() -> None:
    lease = Lease.model_validate(
        {
            "token": "lease-token-1",
            "operation": "extract",
            "attempt": 1,
            "expires_at": 1_000_060,
            "idempotency_key": "run-001:module.shop.checkout:extract:1:snap",
        }
    )
    assert lease.operation == "extract"
    clock = FixedClock()
    assert not lease.expired(clock)
    clock.now = 1_000_061
    assert lease.expired(clock)


def test_store_writes_atomically_and_validates_on_load(tmp_path: Path) -> None:
    from knowledge_compiler.orchestrator.store import RunStore

    store = RunStore(tmp_path / ".knowledge/state/runs")
    record = run()
    store.save(record)
    loaded = store.load("run-001")
    assert loaded == record

    file = tmp_path / ".knowledge/state/runs/run-001/run.json"
    payload = json.loads(file.read_text(encoding="utf-8"))
    payload["targets"][0]["state"] = "hologram"
    file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="state"):
        store.load("run-001")


def test_store_rejects_second_active_run(tmp_path: Path) -> None:
    from knowledge_compiler.orchestrator.store import RunStore

    store = RunStore(tmp_path / ".knowledge/state/runs")
    store.save(run())
    second = run(run_id="run-002")
    with pytest.raises(ValueError, match="active"):
        store.save(second)
    store.save(run(run_id="run-001", active=False))
    store.save(second)
