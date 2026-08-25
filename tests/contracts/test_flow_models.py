from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.contracts.base import ClaimBackedText


ROOT = Path(__file__).resolve().parents[2]


def scope() -> dict:
    return {
        "repository": "fixture/probe-shop",
        "root": "/fixture/probe_repo",
        "branch": "main",
        "commit": "probe-fixture-v1",
        "dirty": False,
        "working_tree_hash": None,
    }


def claim(claim_id: str, statement: str) -> dict:
    return {
        "id": claim_id,
        "statement": statement,
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
    }


def flow_payload() -> dict:
    return {
        "schema_version": "0.1",
        "id": "flow.shop.checkout",
        "type": "flow",
        "title": "Checkout flow",
        "scope": scope(),
        "summary": {
            "text": "A checkout reserves inventory then creates an order.",
            "claim_ids": ["flow.shop.checkout.claim.summary"],
        },
        "trigger": {
            "description": "POST /checkout by the client.",
            "claim_ids": ["flow.shop.checkout.claim.trigger"],
        },
        "steps": [
            {
                "step_id": "step.reserve",
                "order": 1,
                "description": "Reserve inventory for the SKU.",
                "participants": ["checkout-service", "inventory-service"],
                "claim_ids": ["flow.shop.checkout.claim.reserve"],
            },
            {
                "step_id": "step.create-order",
                "order": 2,
                "description": "Create the order identifier.",
                "participants": ["checkout-service"],
                "claim_ids": ["flow.shop.checkout.claim.order"],
            },
        ],
        "failure_paths": [
            {
                "condition": "Reservation returns false.",
                "handling": "Checkout raises ValueError.",
                "claim_ids": ["flow.shop.checkout.claim.failure"],
            }
        ],
        "claims": [
            claim(
                "flow.shop.checkout.claim.summary",
                "A checkout reserves inventory then creates an order.",
            ),
            claim(
                "flow.shop.checkout.claim.trigger",
                "Checkout is triggered by POST /checkout.",
            ),
            claim(
                "flow.shop.checkout.claim.reserve",
                "The first step reserves inventory.",
            ),
            claim(
                "flow.shop.checkout.claim.order",
                "The second step creates the order.",
            ),
            claim(
                "flow.shop.checkout.claim.failure",
                "Failed reservation raises an error.",
            ),
        ],
        "provenance": {
            "execution_mode": "fake",
            "model": "fixture-model-v1",
            "prompt_version": "flow-extraction-v1",
            "schema_version": "0.1",
            "generated_at": "2026-08-25T09:30:00Z",
        },
        "validity": {
            "status": "verified",
            "verified_commit": "probe-fixture-v1",
            "validation_report": ("structural", "semantic"),
        },
    }


def test_flow_round_trips_with_claim_backed_fields() -> None:
    from knowledge_compiler.contracts.knowledge import FlowKnowledge

    payload = flow_payload()
    flow = FlowKnowledge.model_validate(payload)
    assert isinstance(flow.summary, ClaimBackedText)
    assert flow.steps[0].step_id == "step.reserve"
    assert flow.steps[0].participants == ("checkout-service", "inventory-service")
    assert flow == FlowKnowledge.model_validate(flow.model_dump(mode="json"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["summary"].update(
            claim_ids=["flow.shop.checkout.claim.unknown"]
        ),
        lambda p: p["steps"][1].update(participants=[]),
        lambda p: p["trigger"].update(claim_ids=[]),
        lambda p: p.update(id="module.shop.checkout"),
        lambda p: p["claims"].pop(),
    ],
)
def test_flow_rejects_invalid_states(mutation) -> None:
    import copy

    from knowledge_compiler.contracts.knowledge import FlowKnowledge

    payload = copy.deepcopy(flow_payload())
    mutation(payload)
    with pytest.raises(ValueError):
        FlowKnowledge.model_validate(payload)


def test_flow_rejects_duplicate_step_ids_and_gaps() -> None:
    import copy

    from knowledge_compiler.contracts.knowledge import FlowKnowledge

    payload = copy.deepcopy(flow_payload())
    payload["steps"][1]["step_id"] = "step.reserve"
    with pytest.raises(ValueError, match="step"):
        FlowKnowledge.model_validate(payload)

    gapped = copy.deepcopy(flow_payload())
    gapped["steps"][1]["order"] = 7
    with pytest.raises(ValueError, match="order"):
        FlowKnowledge.model_validate(gapped)


def test_flow_ordering_is_input_order_independent() -> None:
    import copy

    from knowledge_compiler.contracts.knowledge import FlowKnowledge

    first = FlowKnowledge.model_validate(flow_payload())
    payload = copy.deepcopy(flow_payload())
    payload["steps"].reverse()
    second = FlowKnowledge.model_validate(payload)
    assert first.model_dump() == second.model_dump()
