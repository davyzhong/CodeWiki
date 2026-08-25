from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts.base import (
    ClaimBackedText,
    Confidence,
    Provenance,
    Relation,
    Scope,
    Validity,
)
from knowledge_compiler.contracts.knowledge import ModuleKnowledge


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/golden/module.yaml"
FIXTURES = ROOT / "tests/fixtures/fake_provider"


def _module_from_golden() -> dict:
    return yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))


def test_shared_models_exist_and_validate() -> None:
    scope = Scope.model_validate(
        {
            "repository": "fixture/probe-shop",
            "root": "/fixture/probe_repo",
            "branch": "main",
            "commit": "probe-fixture-v1",
            "dirty": False,
            "working_tree_hash": None,
        }
    )
    assert scope.commit == "probe-fixture-v1"
    assert Confidence.model_validate(
        {"score": 0.9, "basis": "direct source"}
    ).score == 0.9
    assert Validity.model_validate(
        {"status": "verified", "verified_commit": "probe-fixture-v1"}
    ).status == "verified"
    assert Provenance.model_validate(
        {
            "execution_mode": "fake",
            "model": "fixture-model-v1",
            "prompt_version": "module-extraction-v1",
            "schema_version": "0.1",
            "generated_at": "2026-08-25T09:30:00Z",
        }
    ).model == "fixture-model-v1"
    assert ClaimBackedText.model_validate(
        {"text": "summary", "claim_ids": ["module.a.b.claim.c"]}
    ).claim_ids == ("module.a.b.claim.c",)
    assert Relation.model_validate(
        {
            "predicate": "depends_on",
            "target": "module.shop.inventory",
            "claim_ids": ["module.a.b.claim.c"],
        }
    ).predicate == "depends_on"


def test_target_type_union_accepts_five_types_and_rejects_unknown() -> None:
    from knowledge_compiler.contracts.repository import PlanTarget

    for knowledge_type in (
        "module", "architecture", "flow", "rule", "tech-stack"
    ):
        target = PlanTarget(
            id=f"{knowledge_type}.demo.example", type=knowledge_type, topic="demo"
        )
        assert target.type == knowledge_type
    with pytest.raises(ValueError):
        PlanTarget(id="incident.demo.example", type="incident", topic="demo")


def test_extraction_result_draft_union_rejects_unknown_type() -> None:
    from knowledge_compiler.contracts.knowledge import ExtractionResult

    payload = json.loads(
        (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
    )
    payload["draft"]["scope"]["root"] = "/fixture/probe_repo"
    result = ExtractionResult.model_validate(payload)
    assert result.draft.type == "module"

    payload["draft"]["type"] = "hologram"
    with pytest.raises(ValueError):
        ExtractionResult.model_validate(payload)


def test_module_uses_shared_base_without_golden_drift() -> None:
    payload = _module_from_golden()
    module = ModuleKnowledge.model_validate(payload)
    assert isinstance(module.scope, Scope)
    assert isinstance(module.validity, Validity)
    dumped = yaml.safe_load(
        yaml.safe_dump(
            module.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        )
    )
    assert dumped == payload
