from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts.base import ClaimBackedText


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/golden"


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


def rule_payload() -> dict:
    return {
        "schema_version": "0.1",
        "id": "rule.shop.reservation-first",
        "type": "rule",
        "title": "Reserve before charging",
        "scope": {
            "repository": "fixture/probe-shop",
            "root": "/fixture/probe_repo",
            "branch": "main",
            "commit": "probe-fixture-v1",
            "dirty": False,
            "working_tree_hash": None,
        },
        "summary": {
            "text": "Checkout must reserve inventory before charging.",
            "claim_ids": ["rule.shop.reservation-first.claim.summary"],
        },
        "statement": {
            "text": "Always reserve inventory before creating an order.",
            "claim_ids": ["rule.shop.reservation-first.claim.statement"],
        },
        "severity": "must",
        "applicability": {
            "paths": ["src/shop/checkout.py"],
            "claim_ids": ["rule.shop.reservation-first.claim.applicability"],
        },
        "constraints": [
            {
                "description": "Reservation failures abort checkout.",
                "claim_ids": ["rule.shop.reservation-first.claim.statement"],
            }
        ],
        "exceptions": [],
        "related_objects": ["module.shop.checkout", "flow.shop.checkout"],
        "claims": [
            claim(
                "rule.shop.reservation-first.claim.summary",
                "Checkout must reserve inventory before charging.",
            ),
            claim(
                "rule.shop.reservation-first.claim.statement",
                "Reservation failures abort checkout.",
            ),
            claim(
                "rule.shop.reservation-first.claim.applicability",
                "The rule applies to checkout code.",
            ),
        ],
        "provenance": {
            "execution_mode": "fake",
            "model": "fixture-model-v1",
            "prompt_version": "rule-extraction-v1",
            "schema_version": "0.1",
            "generated_at": "2026-08-25T09:30:00Z",
        },
        "validity": {
            "status": "verified",
            "verified_commit": "probe-fixture-v1",
            "validation_report": ("structural", "semantic"),
        },
    }


def test_rule_round_trips_with_claim_backed_fields() -> None:
    from knowledge_compiler.contracts.knowledge import RuleKnowledge

    rule = RuleKnowledge.model_validate(rule_payload())
    assert isinstance(rule.statement, ClaimBackedText)
    assert rule.severity == "must"
    assert rule.applicability.paths == ("src/shop/checkout.py",)
    assert rule == RuleKnowledge.model_validate(rule.model_dump(mode="json"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(severity="hopefully"),
        lambda p: p["statement"].update(claim_ids=[]),
        lambda p: p["applicability"].update(paths=[]),
        lambda p: p.update(id="flow.shop.reservation"),
        lambda p: p["claims"].pop(),
        lambda p: p["related_objects"].append("module.shop.checkout"),
    ],
)
def test_rule_rejects_invalid_states(mutation) -> None:
    from knowledge_compiler.contracts.knowledge import RuleKnowledge

    payload = copy.deepcopy(rule_payload())
    mutation(payload)
    with pytest.raises(ValueError):
        RuleKnowledge.model_validate(payload)


def test_rule_compiler_renders_only_payload_derived_lines() -> None:
    from knowledge_compiler.compiler.yaml import (
        compile_rule_card,
        compile_rule_yaml,
    )
    from knowledge_compiler.contracts.knowledge import RuleKnowledge

    rule = RuleKnowledge.model_validate(rule_payload())
    (GOLDEN / "rule.yaml").write_bytes(compile_rule_yaml(rule))
    card = compile_rule_card(rule).decode("utf-8")
    for line in card.splitlines():
        stripped = line.strip().lstrip("-# ").strip()
        assert (
            not stripped
            or stripped.startswith(("Reserve", "Always", "Reservation", "must", "Checkout"))
            or "rule.shop.reservation-first" in stripped
            or "src/shop/checkout.py" in stripped
            or stripped.startswith(("Claims:", "Evidence:", "module.", "flow."))
            or stripped in ("Statement", "Applicability", "Constraints", "Exceptions", "Related")
            or stripped == "Reserve before charging"
        ), line
    assert RuleKnowledge.model_validate(
        yaml.safe_load((GOLDEN / "rule.yaml").read_bytes())
    ) == rule
