from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge_compiler.contracts.evidence import SHA256_PATTERN
from knowledge_compiler.contracts.repository import NonBlankString


class ContractModel(BaseModel):
    """Shared frozen base for every canonical knowledge model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        validate_default=True,
    )


class Confidence(ContractModel):
    score: float = Field(strict=True, ge=0.0, le=1.0)
    basis: NonBlankString


class Provenance(ContractModel):
    execution_mode: NonBlankString
    model: NonBlankString
    prompt_version: NonBlankString
    schema_version: Literal["0.1"]
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_explicit_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include an explicit timezone")
        return value


class Scope(ContractModel):
    repository: NonBlankString
    root: Path
    branch: NonBlankString | None
    commit: NonBlankString
    dirty: bool
    working_tree_hash: str | None

    @field_validator("root")
    @classmethod
    def require_absolute_root(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("scope root must be absolute")
        return value

    @field_validator("working_tree_hash")
    @classmethod
    def validate_working_tree_hash(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("working_tree_hash must be a sha256:<64 lowercase hex> hash")
        return value


class ClaimBacked(ContractModel):
    claim_ids: tuple[NonBlankString, ...]

    @field_validator("claim_ids")
    @classmethod
    def require_claim_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("claim_ids must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("duplicate claim_ids are not allowed")
        return tuple(sorted(value))


class ClaimBackedText(ClaimBacked):
    text: NonBlankString


class Relation(ClaimBacked):
    predicate: NonBlankString
    target: NonBlankString


class Validity(ContractModel):
    status: Literal["verified", "stale"]
    verified_commit: NonBlankString
    stale_reason: NonBlankString | None = None
    validation_report: tuple[NonBlankString, ...] = ()

    @model_validator(mode="after")
    def validate_status_details(self) -> Validity:
        if self.status == "verified" and self.stale_reason is not None:
            raise ValueError("verified validity cannot have a stale_reason")
        if self.status == "stale" and self.stale_reason is None:
            raise ValueError("stale validity requires a stale_reason")
        return self


__all__ = [
    "ClaimBacked",
    "ClaimBackedText",
    "Confidence",
    "ContractModel",
    "Provenance",
    "Relation",
    "Scope",
    "Validity",
]
