from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from knowledge_compiler.contracts.evidence import SHA256_PATTERN
from knowledge_compiler.contracts.repository import NonBlankString


MODULE_ID_PATTERN = re.compile(
    r"^module\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$"
)
CLAIM_ID_PATTERN = re.compile(
    r"^module\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*"
    r"\.claim\.[a-z0-9][a-z0-9_-]*$"
)


from knowledge_compiler.contracts.base import (  # noqa: F401
    ClaimBacked as _ClaimBacked,
    ClaimBackedText,
    Confidence,
    Provenance,
    Relation as _RelationBase,
    Scope,
    Validity,
    ContractModel as _ContractModel,
)


class Responsibility(ClaimBackedText):
    pass


class PublicInterface(_ClaimBacked):
    name: NonBlankString
    description: NonBlankString


class Dependency(_ClaimBacked):
    target: NonBlankString
    description: NonBlankString


class Relation(_RelationBase):
    pass


class DraftClaim(_ContractModel):
    id: NonBlankString
    statement: NonBlankString
    evidence_ids: tuple[str, ...]
    confidence: Confidence
    required: bool = True

    @field_validator("id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        if not CLAIM_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "Claim ID must match module.<domain>.<name>.claim.<slug>"
            )
        return value

    @field_validator("evidence_ids")
    @classmethod
    def normalize_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("evidence_ids must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("duplicate Evidence IDs are not allowed")
        if any(not SHA256_PATTERN.fullmatch(item) for item in value):
            raise ValueError("Evidence IDs must be sha256:<64 lowercase hex> hashes")
        return tuple(sorted(value))


class ClaimVerification(_ContractModel):
    status: Literal["supported", "partial", "unsupported", "conflicted"]
    verifier: NonBlankString
    evidence_ids: tuple[str, ...]
    excerpt_hashes: tuple[str, ...]
    verification_request_digest: str

    @model_validator(mode="before")
    @classmethod
    def normalize_evidence_pairs(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        evidence_ids = tuple(data.get("evidence_ids", ()))
        excerpt_hashes = tuple(data.get("excerpt_hashes", ()))
        if len(evidence_ids) == len(excerpt_hashes):
            pairs = sorted(zip(evidence_ids, excerpt_hashes), key=lambda pair: pair[0])
            normalized = dict(data)
            normalized["evidence_ids"] = tuple(pair[0] for pair in pairs)
            normalized["excerpt_hashes"] = tuple(pair[1] for pair in pairs)
            return normalized
        return data

    @field_validator("verification_request_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("verification_request_digest must be a sha256 hash")
        return value

    @model_validator(mode="after")
    def validate_evidence_bindings(self) -> ClaimVerification:
        if not self.evidence_ids:
            raise ValueError("verification evidence_ids must not be empty")
        if len(self.evidence_ids) != len(self.excerpt_hashes):
            raise ValueError("evidence_ids and excerpt_hashes must have equal lengths")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("duplicate Evidence IDs are not allowed")
        if any(not SHA256_PATTERN.fullmatch(item) for item in self.evidence_ids):
            raise ValueError("Evidence IDs must be sha256:<64 lowercase hex> hashes")
        if any(not SHA256_PATTERN.fullmatch(item) for item in self.excerpt_hashes):
            raise ValueError("excerpt_hashes must be sha256:<64 lowercase hex> hashes")
        return self


class Claim(DraftClaim):
    verification: ClaimVerification

    @model_validator(mode="after")
    def verification_must_cover_claim_evidence(self) -> Claim:
        if self.verification.status != "supported":
            raise ValueError("canonical Claim verification must be supported")
        if self.verification.evidence_ids != self.evidence_ids:
            raise ValueError("verification Evidence IDs must match Claim Evidence IDs")
        return self


class _ModulePayload(_ContractModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    type: Literal["module"] = "module"
    title: NonBlankString
    scope: Scope
    summary: ClaimBackedText
    responsibilities: tuple[Responsibility, ...]
    public_interfaces: tuple[PublicInterface, ...]
    dependencies: tuple[Dependency, ...]
    relations: tuple[Relation, ...] = ()
    confidence: Confidence

    _claim_field_names: ClassVar[tuple[str, ...]] = (
        "summary",
        "responsibilities",
        "public_interfaces",
        "dependencies",
        "relations",
    )

    @field_validator("id")
    @classmethod
    def validate_module_id(cls, value: str) -> str:
        if not MODULE_ID_PATTERN.fullmatch(value):
            raise ValueError("module ID must match module.<domain>.<name>")
        return value

    @field_validator("public_interfaces")
    @classmethod
    def normalize_interfaces(
        cls, value: tuple[PublicInterface, ...]
    ) -> tuple[PublicInterface, ...]:
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("duplicate public-interface names are not allowed")
        return tuple(sorted(value, key=lambda item: item.name))

    @field_validator("dependencies")
    @classmethod
    def normalize_dependencies(
        cls, value: tuple[Dependency, ...]
    ) -> tuple[Dependency, ...]:
        targets = [item.target for item in value]
        if len(targets) != len(set(targets)):
            raise ValueError("duplicate dependency targets are not allowed")
        return tuple(sorted(value, key=lambda item: item.target))

    @field_validator("relations")
    @classmethod
    def normalize_relations(cls, value: tuple[Relation, ...]) -> tuple[Relation, ...]:
        keys = [(item.predicate, item.target) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "duplicate relation (predicate, target) keys are not allowed"
            )
        return tuple(sorted(value, key=lambda item: (item.predicate, item.target)))

    def _validate_claim_references(self, known_claim_ids: set[str]) -> None:
        expected_prefix = f"{self.id}.claim."
        foreign = sorted(
            claim_id
            for claim_id in known_claim_ids
            if not claim_id.startswith(expected_prefix)
        )
        if foreign:
            raise ValueError(
                "Claims must belong to the containing Module: " + ", ".join(foreign)
            )
        referenced: list[str] = list(self.summary.claim_ids)
        for field_name in self._claim_field_names[1:]:
            for item in getattr(self, field_name):
                referenced.extend(item.claim_ids)
        unknown = sorted(set(referenced) - known_claim_ids)
        if unknown:
            raise ValueError(f"unknown Claim references: {', '.join(unknown)}")


class DraftModuleKnowledge(_ModulePayload):
    claims: tuple[DraftClaim, ...]

    @field_validator("claims")
    @classmethod
    def normalize_claims(cls, value: tuple[DraftClaim, ...]) -> tuple[DraftClaim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_claim_references(self) -> DraftModuleKnowledge:
        self._validate_claim_references({claim.id for claim in self.claims})
        return self


class ExtractionResult(_ContractModel):
    contract_version: Literal["0.1"]
    run_id: NonBlankString
    target_id: NonBlankString
    operation: Literal["extract"]
    attempt: int = Field(strict=True, gt=0)
    snapshot_id: NonBlankString
    idempotency_key: NonBlankString
    draft: DraftModuleKnowledge
    provenance: Provenance


class ModuleKnowledge(_ModulePayload):
    claims: tuple[Claim, ...]
    provenance: Provenance
    validity: Validity

    @field_validator("claims")
    @classmethod
    def normalize_claims(cls, value: tuple[Claim, ...]) -> tuple[Claim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_canonical_claims(self) -> ModuleKnowledge:
        self._validate_claim_references({claim.id for claim in self.claims})
        if (
            self.validity.status == "verified"
            and self.validity.verified_commit != self.scope.commit
        ):
            raise ValueError(
                "verified validity verified_commit must match the scope commit"
            )
        return self


__all__ = [
    "Claim",
    "ClaimBackedText",
    "ClaimVerification",
    "Confidence",
    "Dependency",
    "DraftClaim",
    "DraftModuleKnowledge",
    "ExtractionResult",
    "ModuleKnowledge",
    "Provenance",
    "PublicInterface",
    "Relation",
    "Responsibility",
    "Scope",
    "Validity",
]
