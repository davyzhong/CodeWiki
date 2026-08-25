from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.contracts.base import ClaimBackedText, Scope


ROOT = Path(__file__).resolve().parents[2]


def scope() -> Scope:
    return Scope.model_validate(
        {
            "repository": "fixture/probe-shop",
            "root": "/fixture/probe_repo",
            "branch": "main",
            "commit": "probe-fixture-v1",
            "dirty": False,
            "working_tree_hash": None,
        }
    )


def architecture_payload() -> dict:
    return {
        "schema_version": "0.1",
        "id": "architecture.shop.platform",
        "type": "architecture",
        "title": "Shop platform architecture",
        "scope": scope().model_dump(mode="json"),
        "summary": {
            "text": "The shop splits checkout and inventory responsibilities.",
            "claim_ids": ["architecture.shop.platform.claim.summary"],
        },
        "components": [
            {
                "name": "checkout-service",
                "responsibility": "Orchestrates checkout.",
                "claim_ids": ["architecture.shop.platform.claim.checkout"],
            },
            {
                "name": "inventory-service",
                "responsibility": "Reserves stock.",
                "claim_ids": ["architecture.shop.platform.claim.summary"],
            },
        ],
        "boundaries": [
            {
                "name": "checkout-to-inventory",
                "description": "Checkout depends on inventory only through reserve.",
                "claim_ids": ["architecture.shop.platform.claim.boundary"],
            }
        ],
        "relationships": [
            {
                "predicate": "depends_on",
                "source": "checkout-service",
                "target": "inventory-service",
                "claim_ids": ["architecture.shop.platform.claim.boundary"],
            }
        ],
        "claims": [
            {
                "id": "architecture.shop.platform.claim.summary",
                "statement": "The shop splits checkout and inventory responsibilities.",
                "evidence_ids": ["sha256:" + "1" * 64],
                "confidence": {"score": 0.9, "basis": "structure"},
                "required": True,
                "verification": {
                    "status": "supported",
                    "verifier": "fixture-verifier-v1",
                    "evidence_ids": ["sha256:" + "1" * 64],
                    "excerpt_hashes": ["sha256:" + "2" * 64],
                    "verification_request_digest": "sha256:" + "3" * 64,
                },
            },
            {
                "id": "architecture.shop.platform.claim.checkout",
                "statement": "checkout-service orchestrates checkout.",
                "evidence_ids": ["sha256:" + "1" * 64],
                "confidence": {"score": 0.9, "basis": "structure"},
                "required": True,
                "verification": {
                    "status": "supported",
                    "verifier": "fixture-verifier-v1",
                    "evidence_ids": ["sha256:" + "1" * 64],
                    "excerpt_hashes": ["sha256:" + "2" * 64],
                    "verification_request_digest": "sha256:" + "3" * 64,
                },
            },
            {
                "id": "architecture.shop.platform.claim.boundary",
                "statement": "Checkout depends on inventory only through reserve.",
                "evidence_ids": ["sha256:" + "1" * 64],
                "confidence": {"score": 0.9, "basis": "structure"},
                "required": True,
                "verification": {
                    "status": "supported",
                    "verifier": "fixture-verifier-v1",
                    "evidence_ids": ["sha256:" + "1" * 64],
                    "excerpt_hashes": ["sha256:" + "2" * 64],
                    "verification_request_digest": "sha256:" + "3" * 64,
                },
            },
        ],
        "provenance": {
            "execution_mode": "fake",
            "model": "fixture-model-v1",
            "prompt_version": "architecture-extraction-v1",
            "schema_version": "0.1",
            "generated_at": "2026-08-25T09:30:00Z",
        },
        "validity": {
            "status": "verified",
            "verified_commit": "probe-fixture-v1",
            "validation_report": ("structural", "semantic"),
        },
    }


def test_architecture_round_trips_with_claim_backed_fields() -> None:
    from knowledge_compiler.contracts.knowledge import ArchitectureKnowledge

    payload = architecture_payload()
    architecture = ArchitectureKnowledge.model_validate(payload)
    assert isinstance(architecture.summary, ClaimBackedText)
    assert architecture.components[0].name == "checkout-service"
    assert architecture.relationships[0].predicate == "depends_on"
    dumped = architecture.model_dump(mode="json")
    assert ArchitectureKnowledge.model_validate(dumped) == architecture


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["components"].append(dict(p["components"][0])),
        lambda p: p["components"][0].update(claim_ids=[]),
        lambda p: p["claims"].pop(),
        lambda p: p.update(id="module.shop.platform"),
    ],
)
def test_architecture_rejects_invalid_states(mutation) -> None:
    from knowledge_compiler.contracts.knowledge import ArchitectureKnowledge

    import copy

    payload = copy.deepcopy(architecture_payload())
    mutation(payload)
    with pytest.raises(ValueError):
        ArchitectureKnowledge.model_validate(payload)


def test_architecture_rejects_unknown_component_references() -> None:
    from knowledge_compiler.contracts.knowledge import ArchitectureKnowledge

    import copy

    payload = copy.deepcopy(architecture_payload())
    payload["relationships"][0]["source"] = "ghost-component"
    with pytest.raises(ValueError, match="component"):
        ArchitectureKnowledge.model_validate(payload)
