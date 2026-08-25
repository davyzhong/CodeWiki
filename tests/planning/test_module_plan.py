from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from knowledge_compiler.contracts.planning import (
    KnowledgePlan,
    PlanRequest,
    PlanTargetSpec,
)
from knowledge_compiler.contracts.evidence import RepositorySurvey
from knowledge_compiler.contracts.repository import (
    RepositorySnapshot,
    build_snapshot_id,
)


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = (ROOT / "tests/fixtures/probe_repo").resolve()
REPOSITORY_ID = "planner-fixture/probe-shop"
COMMIT = "plan-fixture-v1"
SNAPSHOT_ID = build_snapshot_id(REPOSITORY_ID, COMMIT, False, None)


def repository() -> RepositorySnapshot:
    return RepositorySnapshot.model_validate(
        {
            "repository_id": REPOSITORY_ID,
            "snapshot_id": SNAPSHOT_ID,
            "root": REPOSITORY_ROOT,
            "branch": "main",
            "commit": COMMIT,
            "dirty": False,
            "working_tree_hash": None,
            "eligible_files": (
                "src/shop/api.py",
                "src/shop/checkout.py",
                "src/shop/inventory.py",
            ),
        }
    )


def survey(**overrides: object) -> RepositorySurvey:
    values: dict[str, object] = {
        "repository_id": REPOSITORY_ID,
        "snapshot_id": SNAPSHOT_ID,
        "files": ("src/shop/api.py", "src/shop/checkout.py", "src/shop/inventory.py"),
        "languages": ("python",),
        "symbols": ("CheckoutService", "Inventory", "checkout_order"),
        "graph_communities": (("CheckoutService", "Inventory", "checkout_order"),),
        "configuration_facts": {},
    }
    values.update(overrides)
    return RepositorySurvey.model_validate(values)


def plan_request() -> PlanRequest:
    return PlanRequest.model_validate(
        {
            "contract_version": "0.1",
            "run_id": "run-plan-001",
            "repository_id": REPOSITORY_ID,
            "snapshot_id": SNAPSHOT_ID,
            "operation": "plan",
            "attempt": 1,
            "idempotency_key": "run-plan-001:plan:1:" + SNAPSHOT_ID,
        }
    )


def plan_module(request: PlanRequest, repo_survey: RepositorySurvey):
    from knowledge_compiler.planning.module import plan_one_module

    return plan_one_module(request, repo_survey)


def plan_full(request: PlanRequest, repo_survey: RepositorySurvey):
    from knowledge_compiler.planning.module import plan_full_refresh

    return plan_full_refresh(request, repo_survey)


def test_full_refresh_plans_all_five_knowledge_types_without_claims() -> None:
    plan = plan_full(plan_request(), survey())

    assert {spec.target.type for spec in plan.targets} == {
        "architecture",
        "module",
        "flow",
        "rule",
        "tech-stack",
    }
    assert len(plan.targets) == 5
    assert len({spec.target.id for spec in plan.targets}) == 5
    assert "claim" not in json.dumps(plan.model_dump(mode="json")).lower()


def test_full_refresh_plan_is_deterministic() -> None:
    first = plan_full(plan_request(), survey())
    second = plan_full(
        plan_request(),
        survey(
            symbols=("checkout_order", "Inventory", "CheckoutService"),
            files=("src/shop/inventory.py", "src/shop/checkout.py", "src/shop/api.py"),
        ),
    )
    assert first.model_dump() == second.model_dump()


def test_plan_targets_carry_priority_and_requiredness() -> None:
    request = plan_request()
    plan = plan_module(request, survey())
    assert isinstance(plan, KnowledgePlan)
    assert plan.targets
    for spec in plan.targets:
        assert isinstance(spec, PlanTargetSpec)
        assert spec.priority >= 1
        assert isinstance(spec.required, bool)
    top = plan.targets[0]
    assert top.required is True
    assert top.target.type == "module"


def test_plan_is_deterministic_for_equivalent_surveys() -> None:
    request = plan_request()
    first = plan_module(request, survey())
    second = plan_module(
        request,
        survey(
            symbols=("Inventory", "CheckoutService", "checkout_order"),
            files=("src/shop/inventory.py", "src/shop/api.py", "src/shop/checkout.py"),
        ),
    )
    assert first.model_dump() == second.model_dump()


def test_plan_request_result_correlation_fields() -> None:
    request = plan_request()
    plan = plan_module(request, survey())
    for field in (
        "contract_version",
        "run_id",
        "repository_id",
        "snapshot_id",
        "operation",
        "attempt",
        "idempotency_key",
    ):
        assert getattr(plan, field) == getattr(request, field)


def test_plan_rejects_survey_from_foreign_repository() -> None:
    request = plan_request()
    with pytest.raises(ValueError, match="repository"):
        plan_module(
            request,
            survey(
                repository_id="other/repo",
                snapshot_id=build_snapshot_id("other/repo", COMMIT, False, None),
            ),
        )


def test_plan_returns_insufficient_evidence_without_fabrication() -> None:
    from knowledge_compiler.planning.module import InsufficientEvidence

    request = plan_request()
    with pytest.raises(InsufficientEvidence):
        plan_module(
            request,
            survey(symbols=(), graph_communities=(), files=("docs/readme.md",)),
        )


def test_plan_targets_never_carry_claims() -> None:
    request = plan_request()
    plan = plan_module(request, survey())
    dumped = json.dumps(plan.model_dump(mode="json"))
    assert "claim" not in dumped.lower()


def test_plan_requires_deterministic_survey_facts() -> None:
    request = plan_request()
    with pytest.raises(ValueError, match="snapshot"):
        plan_module(request, survey(snapshot_id="sha256:" + "0" * 64))
