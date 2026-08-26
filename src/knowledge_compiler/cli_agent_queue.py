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


def _state_root(repository_root: Path = Path(".")) -> Path:
    return repository_root.resolve() / ".knowledge/state/runs"


def _load_queue(repository_root: Path = Path(".")) -> RunQueue:
    root = _state_root(repository_root)
    store = RunStore(root)
    active = store.active_run()
    if active is None:
        raise typer.Exit(code=1)
    return RunQueue(
        store_root=root, run=active, clock=_FixedWallClock()
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
        RunQueue(
            store_root=_state_root(repository_root),
            run=record,
            clock=_FixedWallClock(),
        )
    except (RunStoreError, QueueError) as error:
        _fail(f"prepare failed: {error}")
    _echo({"run_id": run_id, "target": target})


def next_work(
    operation: Annotated[str, typer.Option()] = "extraction",
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Grant the next lease for the active run."""

    try:
        queue = _load_queue(repository_root)
    except (RunStoreError, typer.Exit):
        _fail("no active run; run prepare first")
        return
    try:
        if operation == "extraction":
            target_id = _next_target(queue, TargetState.EVIDENCE_READY)
            pack = queue.load_evidence_pack(target_id)
            lease = queue.grant_extraction_lease(target_id, ttl=3600)
            request = _extraction_request(queue, target_id, pack)
        elif operation == "verification":
            target_id = _next_target(queue, TargetState.SEMANTIC_PENDING)
            request = _verification_request(queue, target_id)
            lease = queue.grant_verification_lease(target_id, ttl=3600)
        else:
            _fail(f"unknown operation: {operation}")
            return
    except (QueueError, RunStoreError, ValueError, OSError) as error:
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
            "request": request.model_dump(mode="json"),
        }
    )


def evidence(
    target: Annotated[str, typer.Argument()],
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Report the bounded evidence reference for a target."""

    try:
        queue = _load_queue(repository_root)
    except (RunStoreError, typer.Exit):
        _fail("no active run; run prepare first")
        return
    try:
        record = queue.target(target)
    except QueueError:
        _fail(f"unknown target: {target}")
        return
    try:
        pack = queue.load_evidence_pack(target)
    except (RunStoreError, ValueError, OSError) as error:
        _fail(f"evidence unavailable: {error}")
        return
    _echo(
        {
            "target_id": record.target_id,
            "state": record.state.value,
            "evidence_pack": pack.model_dump(mode="json"),
        }
    )


def submit_extraction(
    draft: Annotated[Path, typer.Argument()],
    lease: Annotated[str, typer.Option()],
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Submit an extraction result draft under the granted lease."""

    try:
        queue = _load_queue(repository_root)
        from knowledge_compiler.contracts.knowledge import ExtractionResult

        extraction = ExtractionResult.model_validate_json(
            draft.read_text(encoding="utf-8")
        )
        target_id = extraction.target_id
        record = queue.target(target_id)
        if record.lease is None or record.lease.token != lease:
            raise QueueError("lease token does not match")
        pack = queue.load_evidence_pack(target_id)
        request = _extraction_request(queue, target_id, pack)
        _require_matching_envelope(request, extraction)
        # Building this request performs structural and source/evidence
        # validation before any state is advanced.
        from knowledge_compiler.validation.module import build_verification_request

        build_verification_request(request, extraction, pack.repository.root)
        queue.save_extraction_context(target_id, request, extraction)
        import hashlib

        digest = "sha256:" + hashlib.sha256(
            extraction.model_dump_json().encode("utf-8")
        ).hexdigest()
        record = queue.submit_draft(
            target_id=target_id, lease_token=lease, draft_digest=digest
        )
        record = queue.accept_structural_validation(target_id)
    except (QueueError, RunStoreError, ValueError, OSError) as error:
        _fail(f"submit-extraction failed: {error}")
        return
    _echo({"target_id": record.target_id, "state": record.state.value})


def verify_next(
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Serve ONLY a fresh verification request (no extraction context)."""

    try:
        queue = _load_queue(repository_root)
    except (RunStoreError, typer.Exit):
        _fail("no active run; run prepare first")
        return
    try:
        target_id = _next_target(queue, TargetState.SEMANTIC_PENDING)
        record = queue.target(target_id)
    except QueueError as error:
        _fail(f"verify-next failed: {error}")
        return
    if record.state is not TargetState.SEMANTIC_PENDING:
        _fail(
            "verify-next requires the target to be semantic_pending; "
            f"current state: {record.state.value}"
        )
        return
    try:
        request = _verification_request(queue, target_id)
    except (RunStoreError, ValueError, OSError) as error:
        _fail(f"verify-next failed: {error}")
        return
    _echo({
        "target_id": target_id,
        "context": "fresh-verification-only",
        "request": request.model_dump(mode="json"),
    })


def submit_verification(
    result: Annotated[Path, typer.Argument()],
    lease: Annotated[str, typer.Option()],
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Submit a verification result under the granted lease."""

    try:
        queue = _load_queue(repository_root)
        from knowledge_compiler.contracts.semantic import VerificationResult

        verification = VerificationResult.model_validate_json(
            result.read_text(encoding="utf-8")
        )
        target_id = verification.target_id
        record = queue.target(target_id)
        if record.lease is None or record.lease.token != lease:
            raise QueueError("lease token does not match")
        extraction_request, extraction = queue.load_extraction_context(target_id)
        verification_request = _verification_request(queue, target_id)
        _require_matching_envelope(verification_request, verification)
        pack = extraction_request.evidence_pack
        if extraction.draft.type == "module":
            from knowledge_compiler.validation.module import apply_verification_result

            validated = apply_verification_result(
                extraction_request,
                extraction,
                verification_request,
                verification,
                pack.repository.root,
            )
            canonical = validated.module
            issues = tuple(issue.code for issue in validated.issues)
        else:
            from knowledge_compiler.validation.typed import (
                apply_typed_verification_context,
            )

            validated = apply_typed_verification_context(
                extraction_request=extraction_request,
                extraction=extraction,
                verification_request=verification_request,
                verification_result=verification,
                repository_root=pack.repository.root,
            )
            canonical = validated.canonical
            issues = validated.issues
        if canonical is None:
            raise ValueError(
                "semantic verification rejected the draft: "
                + ", ".join(issues[:20])
            )
        queue.save_verified_artifact(target_id, canonical, pack)
        import hashlib

        digest = "sha256:" + hashlib.sha256(
            verification.model_dump_json().encode("utf-8")
        ).hexdigest()
        record = queue.submit_verification(
            target_id=target_id, lease_token=lease, result_digest=digest
        )
    except (QueueError, RunStoreError, ValueError, OSError) as error:
        _fail(f"submit-verification failed: {error}")
        return
    _echo({"target_id": record.target_id, "state": record.state.value})


def finalize(
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Finalize the active run (publication is orchestrator-owned)."""

    try:
        queue = _load_queue(repository_root)
        incomplete = tuple(
            record.target_id
            for record in queue.record().targets
            if record.required
            and record.state is not TargetState.VERIFIED
            and record.published_object_id is None
        )
        if incomplete:
            raise QueueError(
                "required targets are unfinished: " + ", ".join(incomplete)
            )
        artifacts = tuple(
            queue.load_verified_artifact(record.target_id)
            for record in queue.record().targets
            if record.state is TargetState.VERIFIED
            and record.published_object_id is None
        )
        if not artifacts:
            raise QueueError("no verified artifacts are ready for publication")
        import hashlib

        from knowledge_compiler.storage import GenerationPublisher

        generation = "gen-" + hashlib.sha256(
            queue.record().run_id.encode("utf-8")
        ).hexdigest()[:32]
        published = GenerationPublisher(repository_root.resolve()).publish_generation(
            generation, artifacts
        )
        published_ids = tuple(item.object_id for item in published.objects)
        updated = queue.record()
        for object_id in published_ids:
            record = next(
                item for item in updated.targets if item.target_id == object_id
            )
            updated = updated.with_target(
                record.model_copy(update={"published_object_id": object_id})
            )
        queue.replace_record(updated.model_copy(update={"active": False}))
        report_warning = None
        try:
            _write_final_report(
                repository_root.resolve(),
                run_id=queue.record().run_id,
                generation=generation,
                published_object_ids=published_ids,
            )
        except OSError as error:
            # The manifest is the canonical commit marker. A derived report
            # write failure must not misreport an already committed generation.
            report_warning = f"run report write failed: {error}"
    except (QueueError, RunStoreError, RuntimeError, ValueError, OSError) as error:
        _fail(f"finalize failed: {error}")
        return
    _echo(
        {
            "finalized": True,
            "status": "complete",
            "generation": generation,
            "published_object_ids": list(published_ids),
            "diagnostics": [report_warning] if report_warning else [],
        }
    )


def _next_target(queue: RunQueue, state: TargetState) -> str:
    candidates = sorted(
        (
            record
            for record in queue.record().targets
            if record.state is state and record.lease is None
        ),
        key=lambda record: (record.priority, record.target_id),
    )
    if not candidates:
        raise QueueError(f"no target is ready for {state.value}")
    return candidates[0].target_id


def _extraction_request(queue: RunQueue, target_id: str, pack: object):
    from knowledge_compiler.contracts.semantic import ExtractionRequest

    record = queue.target(target_id)
    if record.lease is None or record.lease.operation != "extract":
        raise QueueError("target holds no extraction lease")
    return ExtractionRequest.model_validate(
        {
            "contract_version": "0.1",
            "run_id": queue.record().run_id,
            "target_id": target_id,
            "operation": "extract",
            "attempt": record.lease.attempt,
            "snapshot_id": queue.record().snapshot_id,
            "idempotency_key": record.lease.idempotency_key,
            "evidence_pack": pack,
        }
    )


def _verification_request(queue: RunQueue, target_id: str):
    from knowledge_compiler.validation.module import build_verification_request

    extraction_request, extraction = queue.load_extraction_context(target_id)
    return build_verification_request(
        extraction_request,
        extraction,
        extraction_request.evidence_pack.repository.root,
    )


def _require_matching_envelope(request: object, result: object) -> None:
    for field in (
        "contract_version",
        "run_id",
        "target_id",
        "operation",
        "attempt",
        "snapshot_id",
        "idempotency_key",
    ):
        if getattr(request, field) != getattr(result, field):
            raise QueueError(f"result envelope mismatch: {field}")
    expected_digest = getattr(request, "verification_request_digest", None)
    if expected_digest is not None and (
        getattr(result, "verification_request_digest", None) != expected_digest
    ):
        raise QueueError("result envelope mismatch: verification_request_digest")


def _write_final_report(
    repository_root: Path,
    *,
    run_id: str,
    generation: str,
    published_object_ids: tuple[str, ...],
) -> None:
    path = repository_root / ".knowledge/state/runs/last-build.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "complete",
        "generation": generation,
        "published_object_ids": list(published_object_ids),
        "diagnostics": [],
        "run_id": run_id,
        "executor": "agent",
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


__all__ = [
    "evidence",
    "finalize",
    "next_work",
    "prepare",
    "submit_extraction",
    "submit_verification",
    "verify_next",
]
