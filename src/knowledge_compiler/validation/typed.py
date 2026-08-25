from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from knowledge_compiler.contracts.base import Validity
from knowledge_compiler.contracts.knowledge import Claim, ClaimVerification
from knowledge_compiler.contracts.semantic import VerificationResult


@dataclass(frozen=True)
class TypedVerificationOutcome:
    canonical: Any | None
    issues: tuple[str, ...]


_DRAFT_TYPES: dict[str, tuple[type, type]] = {}


def _draft_types() -> dict[str, tuple[type, type]]:
    global _DRAFT_TYPES
    if not _DRAFT_TYPES:
        from knowledge_compiler.contracts.knowledge import (
            ArchitectureKnowledge,
            DraftArchitectureKnowledge,
            DraftFlowKnowledge,
            DraftRuleKnowledge,
            DraftTechStackKnowledge,
            FlowKnowledge,
            RuleKnowledge,
            TechStackKnowledge,
        )

        _DRAFT_TYPES = {
            "architecture": (DraftArchitectureKnowledge, ArchitectureKnowledge),
            "flow": (DraftFlowKnowledge, FlowKnowledge),
            "rule": (DraftRuleKnowledge, RuleKnowledge),
            "tech-stack": (DraftTechStackKnowledge, TechStackKnowledge),
        }
    return _DRAFT_TYPES


def apply_typed_verification(
    *,
    draft_payload: dict[str, Any],
    verification_result: VerificationResult | dict[str, Any],
    verifier: str,
) -> TypedVerificationOutcome:
    """Upgrade a typed draft to its canonical form from a supported
    verification result, mirroring the Module apply semantics: every
    required claim must be supported against exactly its cited evidence,
    and the canonical object copies — never regenerates — draft data."""

    try:
        verification = VerificationResult.model_validate(verification_result)
    except ValidationError as error:
        return TypedVerificationOutcome(
            None,
            tuple(
                f"verification.contract@{detail['loc']}: {detail['msg']}"
                for detail in error.errors(include_url=False, include_context=False)
            ),
        )

    draft_type = draft_payload.get("type")
    pair = _draft_types().get(draft_type)
    if pair is None:
        return TypedVerificationOutcome(
            None, (f"unsupported draft type: {draft_type}",)
        )
    draft_model, canonical_model = pair

    claims_payload = [
        {k: v for k, v in claim.items() if k != "verification"}
        for claim in draft_payload.get("claims", [])
    ]
    draft_data = dict(draft_payload)
    draft_data["claims"] = claims_payload
    draft_data["validity"] = None
    try:
        draft = draft_model.model_validate(draft_data)
    except ValidationError as error:
        return TypedVerificationOutcome(
            None,
            tuple(
                f"draft.contract@{detail['loc']}: {detail['msg']}"
                for detail in error.errors(include_url=False, include_context=False)
            ),
        )

    correlation_issues: list[str] = []
    if verification.target_id != draft.id:
        correlation_issues.append(
            f"verification.correlation@target_id: expected {draft.id}, "
            f"got {verification.target_id}"
        )
    if verification.verifications and all(
        item.verification_request_digest
        != verification.verification_request_digest
        for item in verification.verifications[:1]
    ):
        correlation_issues.append(
            "verification.correlation@digest: claim digests do not echo "
            "the result digest"
        )
    if correlation_issues:
        return TypedVerificationOutcome(None, tuple(sorted(correlation_issues)))

    verifications = {item.claim_id: item for item in verification.verifications}
    issues: list[str] = []
    known_claims = {claim.id for claim in draft.claims}
    missing = sorted(known_claims - set(verifications))
    unknown = sorted(set(verifications) - known_claims)
    for claim_id in missing:
        issues.append(f"verification.claim.missing@{claim_id}")
    for claim_id in unknown:
        issues.append(f"verification.claim.unknown@{claim_id}")
    for claim in draft.claims:
        item = verifications.get(claim.id)
        if item is None:
            continue
        if item.status != "supported":
            issues.append(
                f"verification.status@{claim.id}: {item.status} is unsupported"
            )
        if tuple(item.evidence_ids) != claim.evidence_ids:
            issues.append(
                f"verification.evidence.ids@{claim.id}: bindings differ"
            )
    if issues:
        return TypedVerificationOutcome(None, tuple(sorted(issues)))

    canonical_claims = []
    for claim in draft.claims:
        item = verifications[claim.id]
        canonical_claims.append(
            Claim.model_validate(
                {
                    **claim.model_dump(),
                    "verification": ClaimVerification(
                        status=item.status,
                        verifier=verifier,
                        evidence_ids=item.evidence_ids,
                        excerpt_hashes=item.excerpt_hashes,
                        verification_request_digest=(
                            verification.verification_request_digest
                        ),
                    ),
                }
            )
        )
    canonical_payload = draft.model_dump(mode="json")
    canonical_payload["claims"] = [
        claim.model_dump(mode="json") for claim in canonical_claims
    ]
    canonical_payload["validity"] = Validity(
        status="verified",
        verified_commit=draft.scope.commit,
        validation_report=("structural", "semantic"),
    ).model_dump(mode="json")
    try:
        canonical = canonical_model.model_validate(canonical_payload)
    except ValidationError as error:
        return TypedVerificationOutcome(
            None,
            tuple(
                f"canonical.contract@{detail['loc']}: {detail['msg']}"
                for detail in error.errors(include_url=False, include_context=False)
            ),
        )
    return TypedVerificationOutcome(canonical, ())


def apply_typed_verification_context(
    *,
    extraction_request: Any,
    extraction: Any,
    verification_request: Any,
    verification_result: Any,
    repository_root: Any,
) -> TypedVerificationOutcome:
    """Validate the full semantic envelope before canonicalizing a typed draft."""

    from knowledge_compiler.contracts.knowledge import ExtractionResult
    from knowledge_compiler.contracts.semantic import (
        ExtractionRequest,
        VerificationRequest,
    )
    from knowledge_compiler.validation.module import (
        ModuleValidationError,
        build_verification_request,
    )

    try:
        request = ExtractionRequest.model_validate(extraction_request)
        result = ExtractionResult.model_validate(extraction)
        verify_request = VerificationRequest.model_validate(
            verification_request
        )
        verify_result = VerificationResult.model_validate(
            verification_result
        )
        expected_request = build_verification_request(
            request, result, repository_root
        )
    except (ValidationError, ModuleValidationError, ValueError) as error:
        return TypedVerificationOutcome(
            None, (f"typed verification context is invalid: {error}",)
        )

    issues: list[str] = []
    for field in (
        "contract_version",
        "run_id",
        "target_id",
        "operation",
        "attempt",
        "snapshot_id",
        "idempotency_key",
        "verification_request_digest",
    ):
        if getattr(verify_request, field) != getattr(expected_request, field):
            issues.append(f"verification.request.{field}: mismatched")
        if getattr(verify_result, field) != getattr(verify_request, field):
            issues.append(f"verification.result.{field}: mismatched")
    if verify_request.claims != expected_request.claims:
        issues.append("verification.request.claims: mismatched")

    expected_claims = {
        claim.claim_id: claim for claim in expected_request.claims
    }
    actual_claims = {
        claim.claim_id: claim for claim in verify_result.verifications
    }
    if set(expected_claims) != set(actual_claims):
        issues.append("verification.result.claims: incomplete or unknown")
    for claim_id in sorted(set(expected_claims) & set(actual_claims)):
        expected = expected_claims[claim_id]
        actual = actual_claims[claim_id]
        if actual.verification_request_digest != (
            expected_request.verification_request_digest
        ):
            issues.append(f"verification.claim.{claim_id}.digest: mismatched")
        if actual.evidence_ids != tuple(
            item.evidence_id for item in expected.evidence
        ):
            issues.append(f"verification.claim.{claim_id}.evidence: mismatched")
        if actual.excerpt_hashes != tuple(
            item.excerpt_hash for item in expected.evidence
        ):
            issues.append(f"verification.claim.{claim_id}.hashes: mismatched")
        if actual.excerpts != tuple(
            item.excerpt for item in expected.evidence
        ):
            issues.append(f"verification.claim.{claim_id}.excerpts: mismatched")
    verifiers = {item.verifier for item in verify_result.verifications}
    if len(verifiers) != 1:
        issues.append("verification.result.verifier: must be consistent")
    if issues:
        return TypedVerificationOutcome(None, tuple(sorted(issues)))
    return apply_typed_verification(
        draft_payload=result.draft.model_dump(mode="json"),
        verification_result=verify_result,
        verifier=next(iter(verifiers)),
    )


__all__ = [
    "TypedVerificationOutcome",
    "apply_typed_verification",
    "apply_typed_verification_context",
]
