from __future__ import annotations

import pytest

from knowledge_compiler.contracts.relations import (
    CrossTypeRelation,
    RelationRegistry,
)


def relation(
    predicate: str = "involves",
    source: str = "flow.shop.checkout",
    target: str = "module.shop.checkout",
) -> CrossTypeRelation:
    return CrossTypeRelation(
        predicate=predicate,
        source_id=source,
        target_id=target,
        claim_ids=["flow.shop.checkout.claim.summary"],
    )


def registry(*known: str) -> RelationRegistry:
    return RelationRegistry(
        known_object_ids=frozenset(known or ("flow.shop.checkout", "module.shop.checkout"))
    )


def test_relation_accepts_typed_combinations() -> None:
    result = registry().validate(relation())
    assert result.resolved is True
    assert result.unresolved_reason is None


def test_relation_rejects_untyped_predicate() -> None:
    with pytest.raises(ValueError, match="predicate"):
        relation(predicate="smells-like")
    with pytest.raises(ValueError, match="predicate"):
        relation(predicate="involves", source="rule.shop.x", target="module.shop.x")


def test_relation_marks_missing_targets_unresolved_not_fabricated() -> None:
    result = registry("flow.shop.checkout").validate(
        relation(target="module.shop.ghost")
    )
    assert result.resolved is False
    assert result.unresolved_reason == "target-missing"
    assert result.relation.target_id == "module.shop.ghost"


def test_registry_rejects_unknown_source_objects() -> None:
    result = registry("module.shop.checkout").validate(relation())
    assert result.resolved is False
    assert result.unresolved_reason == "source-missing"


def test_registry_indexes_are_deterministic_projections() -> None:
    relations = [
        relation(predicate="involves", target="module.shop.checkout"),
        relation(
            predicate="involves",
            source="flow.shop.checkout",
            target="module.shop.inventory",
        ),
        relation(
            predicate="constrains",
            source="rule.shop.reservation-first",
            target="flow.shop.checkout",
        ),
    ]
    result = RelationRegistry(
        known_object_ids=frozenset(
            {
                "flow.shop.checkout",
                "module.shop.checkout",
                # module.shop.inventory intentionally unknown: the second
                # relation must stay explicitly unresolved.
                "rule.shop.reservation-first",
            }
        )
    ).validate_all(relations)
    outbound = result.outbound_index
    inbound = result.inbound_index
    assert outbound["flow.shop.checkout"] == (
        ("involves", "module.shop.checkout"),
    )
    assert inbound["flow.shop.checkout"] == (
        ("constrains", "rule.shop.reservation-first"),
        ("involves", "flow.shop.checkout"),
    )
    assert result.resolved_relations == 2
    assert len(result.unresolved) == 1
    assert result.unresolved[0].unresolved_reason == "target-missing"
