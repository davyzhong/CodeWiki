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


__all__ = ["TypedVerificationOutcome", "apply_typed_verification"]
