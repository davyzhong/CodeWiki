from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Annotated

import typer

from knowledge_compiler.orchestrator.contracts import RunRecord, TargetState
from knowledge_compiler.orchestrator.queue import QueueError, RunQueue
from knowledge_compiler.orchestrator.store import RunStore, RunStoreError


class _FixedWallClock:
    """Run-lease TTLs use wall seconds; tests inject their own clocks
    through RunQueue directly, so the CLI clock stays simple."""

    def __call__(self) -> int:
        import time

        return int(time.time())


def _state_root() -> Path:
    return Path(".knowledge/state/runs")


def _load_queue() -> RunQueue:
    store = RunStore(_state_root())
    active = store.active_run()
    if active is None:
        raise typer.Exit(code=1)
    return RunQueue(
        store_root=_state_root(), run=active, clock=_FixedWallClock()
    )


def _fail(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED)
    raise typer.Exit(code=1)


def _echo(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def prepare(
    repository_root: Annotated[Path, typer.Option()],
    repository_id: Annotated[str, typer.Option()],
    snapshot_id: Annotated[str, typer.Option()],
    target: Annotated[str, typer.Option()],
    object_type: Annotated[str, typer.Option()] = "module",
) -> None:
    """Create the persisted agent run for one target (queue protocol)."""

    run_id = f"agent-{uuid.uuid4().hex[:12]}"
    record = RunRecord.model_validate(
        {
            "run_id": run_id,
            "repository_id": repository_id,
            "snapshot_id": snapshot_id,
            "executor": "agent",
            "active": True,
            "targets": (
                {
                    "target_id": target,
                    "object_type": object_type,
                    "state": "evidence_ready",
                    "attempt": 1,
                    "repair_attempts": 0,
                    "required": True,
                    "priority": 1,
                    "result": None,
                    "published_object_id": None,
                    "request_digest": "sha256:" + "0" * 64,
                    "result_digest": None,
                    "diagnostics": (),
                    "lease": None,
                },
            ),
        }
    )
    try:
        RunQueue(store_root=_state_root(), run=record, clock=_FixedWallClock())
    except (RunStoreError, QueueError) as error:
        _fail(f"prepare failed: {error}")
    _echo({"run_id": run_id, "target": target})


def next_work(
    operation: Annotated[str, typer.Option()] = "extraction",
) -> None:
    """Grant the next lease for the active run."""

    try:
        queue = _load_queue()
    except (RunStoreError, typer.Exit):
        _fail("no active run; run prepare first")
        return
    target_id = queue.record().targets[0].target_id
    try:
        if operation == "extraction":
            lease = queue.grant_extraction_lease(target_id, ttl=3600)
        elif operation == "verification":
            lease = queue.grant_verification_lease(target_id, ttl=3600)
        else:
            _fail(f"unknown operation: {operation}")
            return
    except QueueError as error:
        _fail(f"next failed: {error}")
        return
    _echo(
        {
            "target_id": target_id,
            "lease": {
                "token": lease.token,
                "operation": lease.operation,
                "attempt": lease.attempt,
                "idempotency_key": lease.idempotency_key,
                "expires_at": lease.expires_at,
            },
        }
    )


def evidence(target: Annotated[str, typer.Argument()]) -> None:
    """Report the bounded evidence reference for a target."""

    try:
        queue = _load_queue()
    except (RunStoreError, typer.Exit):
        _fail("no active run; run prepare first")
        return
    try:
        record = queue.target(target)
    except QueueError:
        _fail(f"unknown target: {target}")
        return
    _echo({"target_id": record.target_id, "state": record.state.value})


def submit_extraction(
    draft: Annotated[Path, typer.Argument()],
    lease: Annotated[str, typer.Option()],
) -> None:
    """Submit an extraction result draft under the granted lease."""

    try:
        queue = _load_queue()
        target_id = queue.record().targets[0].target_id
        import hashlib

        digest = "sha256:" + hashlib.sha256(
            draft.read_bytes()
        ).hexdigest()
        record = queue.submit_draft(
            target_id=target_id, lease_token=lease, draft_digest=digest
        )
    except (QueueError, RunStoreError, OSError) as error:
        _fail(f"submit-extraction failed: {error}")
        return
    _echo({"target_id": record.target_id, "state": record.state.value})


def verify_next() -> None:
    """Serve ONLY a fresh verification request (no extraction context)."""

    try:
        queue = _load_queue()
        target_id = queue.record().targets[0].target_id
        record = queue.target(target_id)
    except (QueueError, RunStoreError):
        _fail("no active run; run prepare first")
        return
    if record.state is not TargetState.SEMANTIC_PENDING:
        _fail(
            "verify-next requires the target to be semantic_pending; "
            f"current state: {record.state.value}"
        )
        return
    _echo(
        {
            "target_id": target_id,
            "context": "fresh-verification-only",
            "note": "Claim-backed fields plus cited redacted evidence; no "
            "extraction conversation is included.",
        }
    )


def submit_verification(
    result: Annotated[Path, typer.Argument()],
    lease: Annotated[str, typer.Option()],
) -> None:
    """Submit a verification result under the granted lease."""

    try:
        queue = _load_queue()
        target_id = queue.record().targets[0].target_id
        record = queue.target(target_id)
        import hashlib

        digest = "sha256:" + hashlib.sha256(
            result.read_bytes()
        ).hexdigest()
        record = record.model_copy(update={"result_digest": digest})
        queue.replace_record(queue.record().with_target(record))
    except (QueueError, RunStoreError, OSError) as error:
        _fail(f"submit-verification failed: {error}")
        return
    _echo({"target_id": record.target_id, "state": record.state.value})


def finalize() -> None:
    """Finalize the active run (publication is orchestrator-owned)."""

    try:
        queue = _load_queue()
        queue.replace_record(
            queue.record().model_copy(update={"active": False})
        )
    except (QueueError, RunStoreError):
        _fail("finalize failed: no active run")
        return
    _echo({"finalized": True})


__all__ = [
    "evidence",
    "finalize",
    "next_work",
    "prepare",
    "submit_extraction",
    "submit_verification",
    "verify_next",
]
