from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from pathlib import Path

from knowledge_compiler.orchestrator.contracts import (
    Clock,
    Lease,
    RunRecord,
    TargetRecord,
    TargetState,
)
from knowledge_compiler.orchestrator.store import RunStore, RunStoreError


class QueueError(ValueError):
    """Raised when a queue operation violates lease or state rules."""


class RunQueue:
    """Lease and idempotency operations over one persisted run."""

    def __init__(
        self,
        *,
        store_root: str | os.PathLike[str],
        run: RunRecord,
        clock: Clock,
    ) -> None:
        self._store = RunStore(store_root)
        self._clock = clock
        self._run = run
        self._store.save(run)

    # -- reads -------------------------------------------------------------

    def record(self) -> RunRecord:
        return self._run

    def target(self, target_id: str) -> TargetRecord:
        for record in self._run.targets:
            if record.target_id == target_id:
                return record
        raise QueueError(f"unknown target: {target_id}")

    def replace_record(self, record: RunRecord) -> None:
        self._run = record
        self._store.save(record)

    def save_extraction_context(
        self, target_id: str, request: object, result: object
    ) -> None:
        self._store.save_extraction_context(
            self._run.run_id, target_id, request, result
        )

    def save_plan(self, plan: object) -> None:
        self._store.save_plan(self._run.run_id, plan)

    def save_evidence_pack(self, target_id: str, pack: object) -> None:
        self._store.save_evidence_pack(self._run.run_id, target_id, pack)

    def load_evidence_pack(self, target_id: str) -> object:
        return self._store.load_evidence_pack(self._run.run_id, target_id)

    def save_verified_artifact(
        self, target_id: str, canonical: object, pack: object
    ) -> None:
        self._store.save_verified_artifact(
            self._run.run_id, target_id, canonical, pack
        )

    def load_verified_artifact(
        self, target_id: str
    ) -> tuple[object, object]:
        return self._store.load_verified_artifact(
            self._run.run_id, target_id
        )

    def load_extraction_context(
        self, target_id: str
    ) -> tuple[object, object]:
        return self._store.load_extraction_context(
            self._run.run_id, target_id
        )

    # -- leases ------------------------------------------------------------

    def grant_extraction_lease(self, target_id: str, *, ttl: int) -> Lease:
        return self._grant(
            target_id,
            required_state=TargetState.EVIDENCE_READY,
            operation="extract",
            next_state=TargetState.EXTRACTION_LEASED,
            ttl=ttl,
        )

    def grant_verification_lease(self, target_id: str, *, ttl: int) -> Lease:
        return self._grant(
            target_id,
            required_state=TargetState.SEMANTIC_PENDING,
            operation="verify",
            next_state=TargetState.VERIFICATION_LEASED,
            ttl=ttl,
        )

    def _grant(
        self,
        target_id: str,
        *,
        required_state: TargetState,
        operation: str,
        next_state: TargetState,
        ttl: int,
    ) -> Lease:
        record = self.target(target_id)
        if record.lease is not None and not record.lease.expired(self._clock):
            raise QueueError(
                f"target is already leased: {target_id} ({record.lease.operation})"
            )
        if record.state is not required_state:
            raise QueueError(
                f"target state {record.state.value} cannot lease {operation}"
            )
        lease = Lease(
            token=secrets.token_urlsafe(24),
            operation=operation,
            attempt=record.attempt + record.repair_attempts,
            expires_at=self._clock() + ttl,
            idempotency_key=(
                f"{self._run.run_id}:{target_id}:{operation}:"
                f"{record.attempt + record.repair_attempts}:{self._run.snapshot_id}"
            ),
        )
        updated = record.transition(next_state).model_copy(
            update={"lease": lease}
        )
        self.replace_record(self._run.with_target(updated))
        return lease

    def expire_leases(self) -> RunRecord | None:
        changed = False
        for record in self._run.targets:
            if record.lease is None or not record.lease.expired(self._clock):
                continue
            prior_state = (
                TargetState.EVIDENCE_READY
                if record.lease.operation == "extract"
                else TargetState.SEMANTIC_PENDING
            )
            # Requeue through the state machine's rollback semantics:
            # leased states legally return to their pre-lease queue state.
            updated = record.model_copy(update={"lease": None}).transition(
                prior_state
            )
            self._run = self._run.with_target(updated)
            changed = True
        if changed:
            self._store.save(self._run)
            return self._run
        return None

    # -- submissions ---------------------------------------------------------

    def submit_draft(
        self, *, target_id: str, lease_token: str, draft_digest: str
    ) -> TargetRecord:
        record = self._consume_lease(target_id, lease_token, "extract")
        updated = record.transition(TargetState.DRAFT_SUBMITTED).model_copy(
            update={"result_digest": draft_digest, "lease": None}
        )
        self.replace_record(self._run.with_target(updated))
        return updated

    def accept_structural_validation(self, target_id: str) -> TargetRecord:
        """Orchestrator-owned transition through structural validation."""

        record = self.target(target_id)
        updated = record.transition(TargetState.STRUCTURAL_VALIDATED)
        updated = updated.transition(TargetState.SEMANTIC_PENDING)
        self.replace_record(self._run.with_target(updated))
        return updated

    def submit_verification(
        self, *, target_id: str, lease_token: str, result_digest: str
    ) -> TargetRecord:
        record = self._consume_lease(target_id, lease_token, "verify")
        updated = record.transition(TargetState.VERIFIED).model_copy(
            update={
                "result_digest": result_digest,
                "lease": None,
                "published_object_id": None,
            }
        )
        self.replace_record(self._run.with_target(updated))
        return updated

    def replay_verification(
        self, *, target_id: str, result_digest: str
    ) -> TargetRecord:
        record = self.target(target_id)
        if record.result_digest != result_digest:
            raise QueueError(
                "replayed payload differs from the recorded result digest"
            )
        return record

    def replay_extraction(
        self, *, target_id: str, draft_digest: str
    ) -> TargetRecord:
        record = self.target(target_id)
        if record.result_digest is None:
            raise QueueError("no recorded extraction result to replay")
        if record.result_digest != draft_digest:
            raise QueueError(
                "replayed payload differs from the recorded result digest"
            )
        return record

    def _consume_lease(
        self, target_id: str, lease_token: str, operation: str
    ) -> TargetRecord:
        record = self.target(target_id)
        if record.lease is None:
            raise QueueError(f"target holds no lease: {target_id}")
        if record.lease.token != lease_token:
            raise QueueError("lease token does not match")
        if record.lease.operation != operation:
            raise QueueError("lease operation mismatch")
        if record.lease.expired(self._clock):
            raise QueueError("lease expired")
        return record


__all__ = ["QueueError", "RunQueue"]
