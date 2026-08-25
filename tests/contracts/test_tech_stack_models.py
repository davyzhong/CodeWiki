from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts.knowledge import TechStackKnowledge


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/golden"


def claim(claim_id: str) -> dict:
    return {
        "id": claim_id,
        "statement": "The project uses the technology.",
        "evidence_ids": ["sha256:" + "1" * 64],
        "confidence": {"score": 0.9, "basis": "manifest"},
        "required": True,
        "verification": {
            "status": "supported",
            "verifier": "fixture-verifier-v1",
            "evidence_ids": ["sha256:" + "1" * 64],
            "excerpt_hashes": ["sha256:" + "2" * 64],
            "verification_request_digest": "sha256:" + "3" * 64,
        },
    }


def tech_stack_payload() -> dict:
    return {
        "schema_version": "0.1",
        "id": "tech-stack.shop.platform",
        "type": "tech-stack",
        "title": "Shop platform stack",
        "scope": {
            "repository": "fixture/probe-shop",
            "root": "/fixture/probe_repo",
            "branch": "main",
            "commit": "probe-fixture-v1",
            "dirty": False,
            "working_tree_hash": None,
        },
        "summary": {
            "text": "The shop runs on Python with Pydantic.",
            "claim_ids": ["tech-stack.shop.platform.claim.summary"],
        },
        "entries": [
            {
                "name": "python",
                "category": "language",
                "version": "3.12",
                "scope": "runtime",
                "claim_ids": [
                    "tech-stack.shop.platform.claim.python-version"
                ],
            },
            {
                "name": "pydantic",
                "category": "library",
                "version": "unknown",
                "scope": "dependency",
                "claim_ids": [
                    "tech-stack.shop.platform.claim.pydantic-usage"
                ],
            },
        ],
        "configurations": [
            {
                "path": "pyproject.toml",
                "description": "Declares the runtime and dependencies.",
                "claim_ids": [
                    "tech-stack.shop.platform.claim.python-version"
                ],
            }
        ],
        "claims": [
            claim("tech-stack.shop.platform.claim.summary"),
            claim("tech-stack.shop.platform.claim.python-version"),
            claim("tech-stack.shop.platform.claim.pydantic-usage"),
        ],
        "provenance": {
            "execution_mode": "fake",
            "model": "fixture-model-v1",
            "prompt_version": "tech-stack-extraction-v1",
            "schema_version": "0.1",
            "generated_at": "2026-08-25T09:30:00Z",
        },
        "validity": {
            "status": "verified",
            "verified_commit": "probe-fixture-v1",
            "validation_report": ("structural", "semantic"),
        },
    }


def test_tech_stack_round_trips_with_claim_backed_entries() -> None:
    payload = tech_stack_payload()
    stack = TechStackKnowledge.model_validate(payload)
    assert stack.entries[0].version == "3.12"
    assert stack.entries[1].version == "unknown"
    assert stack == TechStackKnowledge.model_validate(stack.model_dump(mode="json"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["entries"][0].update(version="latest"),
        lambda p: p["entries"][0].update(claim_ids=[]),
        lambda p: p["entries"][1].update(name="python"),
        lambda p: p.update(id="rule.shop.platform"),
        lambda p: p["claims"].pop(),
        lambda p: p["configurations"][0].update(path="../escape.toml"),
    ],
)
def test_tech_stack_rejects_invalid_states(mutation) -> None:
    payload = copy.deepcopy(tech_stack_payload())
    mutation(payload)
    with pytest.raises(ValueError):
        TechStackKnowledge.model_validate(payload)


def test_tech_stack_compiler_goldens() -> None:
    from knowledge_compiler.compiler.yaml import (
        compile_tech_stack_card,
        compile_tech_stack_yaml,
    )

    stack = TechStackKnowledge.model_validate(tech_stack_payload())
    (GOLDEN / "tech-stack.yaml").write_bytes(compile_tech_stack_yaml(stack))
    canonical = compile_tech_stack_yaml(stack)
    assert canonical == (GOLDEN / "tech-stack.yaml").read_bytes()
    assert TechStackKnowledge.model_validate(
        yaml.safe_load(canonical)
    ) == stack
    card = compile_tech_stack_card(stack).decode("utf-8")
    assert "python" in card
    assert "3.12" in card
    assert "unknown" in card
