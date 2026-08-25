from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge_compiler.contracts.evidence import EvidencePack, SHA256_PATTERN
from knowledge_compiler.contracts.knowledge import ExtractionResult
from knowledge_compiler.contracts.repository import NonBlankString


class _SemanticModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always", validate_default=True
    )


class ExtractionRequest(_SemanticModel):
    contract_version: Literal["0.1"]
    run_id: NonBlankString
    target_id: NonBlankString
    operation: Literal["extract"]
    attempt: int = Field(strict=True, gt=0)
    snapshot_id: NonBlankString
    idempotency_key: NonBlankString
    evidence_pack: EvidencePack


class VerificationEvidence(_SemanticModel):
    evidence_id: str
    excerpt_hash: str
    excerpt: str

    @field_validator("evidence_id", "excerpt_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("must be a sha256:<64 lowercase hex> hash")
        return value


class VerificationClaim(_SemanticModel):
    claim_id: NonBlankString
    statement: NonBlankString
    evidence: tuple[VerificationEvidence, ...]

    @field_validator("evidence")
    @classmethod
    def normalize_evidence(
        cls, value: tuple[VerificationEvidence, ...]
    ) -> tuple[VerificationEvidence, ...]:
        if not value:
            raise ValueError("verification Claim evidence must not be empty")
        ids = [item.evidence_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate verification Evidence IDs are not allowed")
        return tuple(sorted(value, key=lambda item: item.evidence_id))


class VerificationRequest(_SemanticModel):
    contract_version: Literal["0.1"]
    run_id: NonBlankString
    target_id: NonBlankString
    operation: Literal["verify"]
    attempt: int = Field(strict=True, gt=0)
    snapshot_id: NonBlankString
    idempotency_key: NonBlankString
    claims: tuple[VerificationClaim, ...]
    verification_request_digest: str

    @field_validator("claims")
    @classmethod
    def normalize_claims(
        cls, value: tuple[VerificationClaim, ...]
    ) -> tuple[VerificationClaim, ...]:
        if not value:
            raise ValueError("verification claims must not be empty")
        ids = [item.claim_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate verification Claim IDs are not allowed")
        return tuple(sorted(value, key=lambda item: item.claim_id))

    @field_validator("verification_request_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("verification_request_digest must be a sha256 hash")
        return value


class ClaimVerificationResult(_SemanticModel):
    claim_id: NonBlankString
    status: Literal["supported", "partial", "unsupported", "conflicted"]
    verifier: NonBlankString
    evidence_ids: tuple[str, ...]
    excerpt_hashes: tuple[str, ...]
    excerpts: tuple[str, ...]
    verification_request_digest: str

    @model_validator(mode="before")
    @classmethod
    def normalize_evidence_bindings(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        ids = tuple(data.get("evidence_ids", ()))
        hashes = tuple(data.get("excerpt_hashes", ()))
        excerpts = tuple(data.get("excerpts", ()))
        if len(ids) == len(hashes) == len(excerpts):
            triples = sorted(zip(ids, hashes, excerpts), key=lambda item: item[0])
            normalized = dict(data)
            normalized["evidence_ids"] = tuple(item[0] for item in triples)
            normalized["excerpt_hashes"] = tuple(item[1] for item in triples)
            normalized["excerpts"] = tuple(item[2] for item in triples)
            return normalized
        return data

    @model_validator(mode="after")
    def validate_parallel_evidence(self) -> ClaimVerificationResult:
        lengths = {len(self.evidence_ids), len(self.excerpt_hashes), len(self.excerpts)}
        if lengths == {0} or len(lengths) != 1:
            raise ValueError("verification evidence fields must be non-empty and equal length")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("duplicate verification Evidence IDs are not allowed")
        if any(not SHA256_PATTERN.fullmatch(value) for value in self.evidence_ids):
            raise ValueError("evidence_ids must contain sha256 hashes")
        if any(not SHA256_PATTERN.fullmatch(value) for value in self.excerpt_hashes):
            raise ValueError("excerpt_hashes must contain sha256 hashes")
        if not SHA256_PATTERN.fullmatch(self.verification_request_digest):
            raise ValueError("verification_request_digest must be a sha256 hash")
        return self


class VerificationResult(_SemanticModel):
    contract_version: Literal["0.1"]
    run_id: NonBlankString
    target_id: NonBlankString
    operation: Literal["verify"]
    attempt: int = Field(strict=True, gt=0)
    snapshot_id: NonBlankString
    idempotency_key: NonBlankString
    verification_request_digest: str
    verifications: tuple[ClaimVerificationResult, ...]

    @field_validator("verification_request_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("verification_request_digest must be a sha256 hash")
        return value

    @field_validator("verifications")
    @classmethod
    def normalize_verifications(
        cls, value: tuple[ClaimVerificationResult, ...]
    ) -> tuple[ClaimVerificationResult, ...]:
        ids = [item.claim_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate verification Claim IDs are not allowed")
        return tuple(sorted(value, key=lambda item: item.claim_id))


__all__ = [
    "ClaimVerificationResult",
    "ExtractionRequest",
    "ExtractionResult",
    "VerificationClaim",
    "VerificationEvidence",
    "VerificationRequest",
    "VerificationResult",
]
