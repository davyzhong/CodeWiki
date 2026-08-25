from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def draft_for(type_name: str) -> tuple:
    import sys

    sys.path.insert(0, str(ROOT / "tests/contracts"))
    from test_architecture_models import architecture_payload
    from test_flow_models import flow_payload
    from test_rule_models import rule_payload
    from test_tech_stack_models import tech_stack_payload

    payloads = {
        "architecture": architecture_payload,
        "flow": flow_payload,
        "rule": rule_payload,
        "tech-stack": tech_stack_payload,
    }
    payload = payloads[type_name]()
    claims = [
        {k: v for k, v in claim.items() if k != "verification"}
        for claim in payload["claims"]
    ]
    return payload, claims


def verification_for(claims: list[dict], digest: str) -> dict:
    return {
        "contract_version": "0.1",
        "run_id": "typed-run-001",
        "target_id": "typed-target",
        "operation": "verify",
        "attempt": 1,
        "snapshot_id": "typed-snapshot",
        "idempotency_key": "typed-run-001:typed-target:verify:1:typed-snapshot",
        "verification_request_digest": digest,
        "verifications": [
            {
                "claim_id": claim["id"],
                "status": "supported",
                "verifier": "typed-verifier-v1",
                "evidence_ids": list(claim["evidence_ids"]),
                "excerpt_hashes": ["sha256:" + "2" * 64]
                * len(claim["evidence_ids"]),
                "excerpts": ["excerpt"] * len(claim["evidence_ids"]),
                "verification_request_digest": digest,
            }
            for claim in claims
        ],
    }


@pytest.mark.parametrize("type_name", ("architecture", "flow", "rule", "tech-stack"))
def test_typed_apply_builds_canonical_from_supported_draft(type_name: str) -> None:
    from knowledge_compiler.contracts.knowledge import (
        ArchitectureKnowledge,
        FlowKnowledge,
        RuleKnowledge,
        TechStackKnowledge,
    )
    from knowledge_compiler.validation.typed import apply_typed_verification

    canonical_types = {
        "architecture": ArchitectureKnowledge,
        "flow": FlowKnowledge,
        "rule": RuleKnowledge,
        "tech-stack": TechStackKnowledge,
    }
    payload, claims = draft_for(type_name)
    digest = "sha256:" + "4" * 64
    verification = verification_for(claims, digest)

    result = apply_typed_verification(
        draft_payload=payload,
        verification_result=verification,
        verifier="typed-verifier-v1",
    )
    assert result.canonical is not None
    assert isinstance(result.canonical, canonical_types[type_name])
    assert result.canonical.validity.status == "verified"
    for claim in result.canonical.claims:
        assert claim.verification.status == "supported"


def test_typed_apply_rejects_unsupported_claims() -> None:
    from knowledge_compiler.validation.typed import apply_typed_verification

    payload, claims = draft_for("rule")
    digest = "sha256:" + "4" * 64
    verification = verification_for(claims, digest)
    verification["verifications"][0]["status"] = "unsupported"

    result = apply_typed_verification(
        draft_payload=payload,
        verification_result=verification,
        verifier="typed-verifier-v1",
    )
    assert result.canonical is None
    assert any("unsupported" in issue for issue in result.issues)


def test_typed_apply_rejects_missing_claim_verification() -> None:
    from knowledge_compiler.validation.typed import apply_typed_verification

    payload, claims = draft_for("flow")
    digest = "sha256:" + "4" * 64
    verification = verification_for(claims, digest)
    verification["verifications"].pop()

    result = apply_typed_verification(
        draft_payload=payload,
        verification_result=verification,
        verifier="typed-verifier-v1",
    )
    assert result.canonical is None
    assert result.issues
