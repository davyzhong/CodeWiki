from __future__ import annotations

import re

import pytest

from knowledge_compiler.contracts.evidence import RepositorySurvey
from knowledge_compiler.contracts.planning import PlanRequest
from knowledge_compiler.planning.module import (
    MAX_TARGET_COUNT,
    InsufficientEvidence,
    plan_full_refresh,
)


def _request() -> PlanRequest:
    return PlanRequest(
        run_id="survey-plan-001",
        repository_id="example/Order Service",
        snapshot_id="snapshot-001",
        attempt=1,
        idempotency_key="survey-plan-001:plan:1:snapshot-001",
    )


def _survey(*, reversed_evidence: bool = False) -> RepositorySurvey:
    files = (
        "src/orders/checkout.py",
        "src/payments/gateway.py",
        "pyproject.toml",
    )
    languages = ("Python", "TOML")
    symbols = (
        "CheckoutService",
        "Inventory.reserve",
        "PaymentGateway.capture",
        "PaymentPolicy.authorize",
    )
    communities = (
        ("CheckoutService", "Inventory.reserve"),
        ("PaymentGateway.capture", "PaymentPolicy.authorize"),
    )
    flow_facts = [
        ("flow.checkout", "checkout_order"),
        ("flow.payment", "PaymentGateway.capture"),
    ]
    rule_facts = [
        ("rule.inventory", "Inventory.reserve"),
        ("rule.payment", "PaymentPolicy.authorize"),
    ]
    if reversed_evidence:
        files = tuple(reversed(files))
        languages = tuple(reversed(languages))
        symbols = tuple(reversed(symbols))
        communities = tuple(tuple(reversed(group)) for group in reversed(communities))
        flow_facts = list(reversed(flow_facts))
        rule_facts = list(reversed(rule_facts))
    return RepositorySurvey(
        repository_id="example/Order Service",
        snapshot_id="snapshot-001",
        files=files,
        languages=languages,
        symbols=symbols,
        graph_communities=communities,
        configuration_facts=dict(
            rule_facts + flow_facts + [("python_requires", ">=3.12")]
        ),
    )


def test_full_refresh_discovers_stable_targets_from_distinct_survey_groups() -> None:
    first = plan_full_refresh(_request(), _survey())
    reordered = plan_full_refresh(_request(), _survey(reversed_evidence=True))

    assert len(first.targets) > 5
    assert len(first.targets) <= MAX_TARGET_COUNT
    assert first.model_dump() == reordered.model_dump()
    assert [spec.target.id for spec in first.targets] == [
        spec.target.id for spec in sorted(
            first.targets,
            key=lambda spec: (spec.priority, spec.target.id),
        )
    ]
    assert all(
        re.fullmatch(r"[a-z0-9][a-z0-9.-]*", spec.target.id)
        for spec in first.targets
    )

    modules = [spec.target for spec in first.targets if spec.target.type == "module"]
    assert len(modules) == 2
    assert len({target.id for target in modules}) == 2
    assert len({target.evidence_seeds for target in modules}) == 2
    assert {target.evidence_seeds for target in modules} == {
        ("CheckoutService", "Inventory.reserve"),
        ("PaymentGateway.capture", "PaymentPolicy.authorize"),
    }
    assert sum(spec.target.type == "architecture" for spec in first.targets) == 1
    assert sum(spec.target.type == "tech-stack" for spec in first.targets) == 1


def _boundary_survey(**overrides: object) -> RepositorySurvey:
    values: dict[str, object] = {
        "repository_id": "example/Order Service",
        "snapshot_id": "snapshot-001",
        "files": (),
        "languages": (),
        "symbols": (),
        "graph_communities": (),
        "configuration_facts": {},
    }
    values.update(overrides)
    return RepositorySurvey.model_validate(values)


def _targets_of_type(plan, object_type: str):
    return [spec.target for spec in plan.targets if spec.target.type == object_type]


def test_full_refresh_preserves_communities_that_share_first_three_seeds() -> None:
    plan = plan_full_refresh(
        _request(),
        _boundary_survey(
            graph_communities=(
                ("Alpha", "Beta", "Common", "Delta"),
                ("Alpha", "Beta", "Common", "Echo"),
            )
        ),
    )

    modules = _targets_of_type(plan, "module")
    assert len(modules) == 2
    assert len({target.id for target in modules}) == 2
    assert {target.evidence_seeds for target in modules} == {
        ("Alpha", "Beta", "Common"),
    }


def test_full_refresh_deduplicates_exact_graph_communities() -> None:
    plan = plan_full_refresh(
        _request(),
        _boundary_survey(
            graph_communities=(
                ("Checkout", "Inventory", "Orders"),
                ("Orders", "Checkout", "Inventory"),
            )
        ),
    )

    modules = _targets_of_type(plan, "module")
    assert len(modules) == 1
    assert modules[0].evidence_seeds == ("Checkout", "Inventory", "Orders")


def test_full_refresh_disambiguates_safe_slug_collisions() -> None:
    plan = plan_full_refresh(
        _request(),
        _boundary_survey(
            graph_communities=(("Payments API",), ("Payments-API",))
        ),
    )

    module_ids = [target.id for target in _targets_of_type(plan, "module")]
    assert len(module_ids) == 2
    assert len(set(module_ids)) == 2
    assert all(
        target_id.startswith("module.order-service.payments-api-")
        for target_id in module_ids
    )


def test_full_refresh_enforces_each_discovery_type_cap() -> None:
    configuration_facts = {
        **{f"flow.{index:02d}": f"Flow{index:02d}" for index in range(10)},
        **{f"rule.{index:02d}": f"Rule{index:02d}" for index in range(10)},
    }
    plan = plan_full_refresh(
        _request(),
        _boundary_survey(
            graph_communities=tuple((f"Module{index:02d}",) for index in range(10)),
            configuration_facts=configuration_facts,
        ),
    )

    assert len(_targets_of_type(plan, "module")) == 8
    assert len(_targets_of_type(plan, "flow")) == 7
    assert len(_targets_of_type(plan, "rule")) == 7
    assert len(plan.targets) == MAX_TARGET_COUNT


@pytest.mark.parametrize(
    ("survey_overrides", "expected_seeds"),
    (
        (
            {"graph_communities": (("GraphOnly", "Dependency"),)},
            ("Dependency", "GraphOnly"),
        ),
        ({"symbols": ("SymbolOnly",)}, ("SymbolOnly",)),
        ({"files": ("src/file_only.py",)}, ("src/file_only.py",)),
    ),
)
def test_full_refresh_supports_sparse_module_evidence_fallbacks(
    survey_overrides: dict[str, object], expected_seeds: tuple[str, ...]
) -> None:
    plan = plan_full_refresh(_request(), _boundary_survey(**survey_overrides))

    modules = _targets_of_type(plan, "module")
    assert len(modules) == 1
    assert modules[0].evidence_seeds == expected_seeds
    assert {spec.target.type for spec in plan.targets} == {
        "architecture",
        "module",
        "flow",
        "rule",
        "tech-stack",
    }


def test_full_refresh_rejects_a_survey_without_any_module_evidence() -> None:
    with pytest.raises(InsufficientEvidence, match="evidence"):
        plan_full_refresh(_request(), _boundary_survey(languages=("Python",)))
