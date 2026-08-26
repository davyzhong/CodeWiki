from __future__ import annotations

import re

from knowledge_compiler.contracts.evidence import RepositorySurvey
from knowledge_compiler.contracts.planning import PlanRequest
from knowledge_compiler.planning.module import MAX_TARGET_COUNT, plan_full_refresh


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
