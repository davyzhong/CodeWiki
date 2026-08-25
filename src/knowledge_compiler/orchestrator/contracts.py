from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge_compiler.contracts.repository import NonBlankString


Clock = Callable[[], int]

_MAX_REPAIR_ATTEMPTS = 2


class TargetState(str, Enum):
    QUEUED = "queued"
    EVIDENCE_READY = "evidence_ready"
    EXTRACTION_LEASED = "extraction_leased"
    DRAFT_SUBMITTED = "draft_submitted"
    STRUCTURAL_VALIDATED = "structural_validated"
    SEMANTIC_PENDING = "semantic_pending"
    VERIFICATION_LEASED = "verification_leased"
    VERIFIED = "verified"
    REPAIR_PENDING = "repair_pending"
    DONE = "done"


class TerminalResult(str, Enum):
    INVALID = "invalid"
    CONFLICTED = "conflicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    RETIRED = "retired"
    SKIPPED = "skipped"


_LEGAL_TRANSITIONS: dict[TargetState, frozenset[TargetState]] = {
    TargetState.QUEUED: frozenset({TargetState.EVIDENCE_READY, TargetState.DONE}),
    TargetState.EVIDENCE_READY: frozenset(
        {TargetState.EXTRACTION_LEASED, TargetState.DONE}
    ),
    TargetState.EXTRACTION_LEASED: frozenset(
        {
            TargetState.DRAFT_SUBMITTED,
            TargetState.REPAIR_PENDING,
            # Lease-expiry rollback returns the target to its pre-lease
            # queue state without losing accepted results.
            TargetState.EVIDENCE_READY,
            TargetState.DONE,
        }
    ),
    TargetState.DRAFT_SUBMITTED: frozenset(
        {TargetState.STRUCTURAL_VALIDATED, TargetState.REPAIR_PENDING, TargetState.DONE}
    ),
    TargetState.STRUCTURAL_VALIDATED: frozenset(
        {TargetState.SEMANTIC_PENDING, TargetState.REPAIR_PENDING, TargetState.DONE}
    ),
    TargetState.SEMANTIC_PENDING: frozenset(
        {TargetState.VERIFICATION_LEASED, TargetState.DONE}
    ),
    TargetState.VERIFICATION_LEASED: frozenset(
        {
            TargetState.VERIFIED,
            TargetState.REPAIR_PENDING,
            TargetState.SEMANTIC_PENDING,
            TargetState.DONE,
        }
    ),
    TargetState.REPAIR_PENDING: frozenset(
        {TargetState.EXTRACTION_LEASED, TargetState.DONE}
    ),
    TargetState.VERIFIED: frozenset({TargetState.DONE}),
    TargetState.DONE: frozenset(),
}


class Lease(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    token: NonBlankString
    operation: Literal["extract", "verify"]
    attempt: int = Field(strict=True, gt=0)
    expires_at: int = Field(strict=True, ge=0)
    idempotency_key: NonBlankString

    def expired(self, clock: Clock) -> bool:
        return clock() > self.expires_at


class TargetRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    target_id: NonBlankString
    object_type: Literal["module", "architecture", "flow", "rule", "tech-stack"]
    topic: NonBlankString | None = None
    evidence_seeds: tuple[NonBlankString, ...] = ()
    state: TargetState = TargetState.QUEUED
    attempt: int = Field(strict=True, gt=0)
    repair_attempts: int = Field(strict=True, ge=0)
    required: bool = True
    priority: int = Field(strict=True, ge=1, le=9)
    result: TerminalResult | None = None
    published_object_id: NonBlankString | None = None
    request_digest: NonBlankString
    result_digest: NonBlankString | None = None
    diagnostics: tuple[str, ...] = ()
    lease: Lease | None = None

    @model_validator(mode="after")
    def terminal_state_agrees_with_result(self) -> "TargetRecord":
        if self.state is TargetState.DONE and self.result is None:
            raise ValueError("done targets require a terminal result")
        if self.state is not TargetState.DONE and self.result is not None:
            raise ValueError("only done targets carry a result")
        return self

    def transition(self, next_state: TargetState) -> "TargetRecord":
        if self.state is TargetState.DONE:
            raise ValueError("terminal targets cannot transition")
        if next_state not in _LEGAL_TRANSITIONS[self.state]:
            raise ValueError(
                f"illegal transition {self.state.value} -> {next_state.value}"
            )
        repair_attempts = self.repair_attempts
        if (
            self.state is TargetState.REPAIR_PENDING
            and next_state is TargetState.EXTRACTION_LEASED
        ):
            if self.repair_attempts >= _MAX_REPAIR_ATTEMPTS:
                raise ValueError("repair attempts exhausted")
            repair_attempts += 1
        return self.model_copy(
            update={"state": next_state, "repair_attempts": repair_attempts}
        )

    def finish(
        self, result: TerminalResult, *, diagnostics: tuple[str, ...] = ()
    ) -> "TargetRecord":
        return self.model_copy(
            update={
                "state": TargetState.DONE,
                "result": result,
                "diagnostics": diagnostics,
                "lease": None,
            }
        )


class RunRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    run_id: NonBlankString
    repository_id: NonBlankString
    snapshot_id: NonBlankString
    executor: Literal["llm", "agent"]
    active: bool = True
    targets: tuple[TargetRecord, ...] = ()

    @model_validator(mode="after")
    def unique_targets(self) -> "RunRecord":
        ids = [record.target_id for record in self.targets]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate target ids in one run")
        return self

    def with_target(self, record: TargetRecord) -> "RunRecord":
        replaced = {
            existing.target_id: existing for existing in self.targets
        }
        replaced[record.target_id] = record
        return self.model_copy(
            update={
                "targets": tuple(
                    sorted(replaced.values(), key=lambda item: item.target_id)
                )
            }
        )


__all__ = [
    "Clock",
    "Lease",
    "RunRecord",
    "TargetRecord",
    "TargetState",
    "TerminalResult",
]
