from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from knowledge_compiler.contracts.repository import NonBlankString


class _RelationModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )


# Typed predicate table: predicate -> allowed (source_type, target_type)
# combinations. Untyped predicates and unlisted combinations are rejected.
RELATION_RULES: dict[str, frozenset[tuple[str, str]]] = {
    "involves": frozenset(
        {
            ("flow", "module"),
            ("flow", "architecture"),
            ("flow", "tech-stack"),
        }
    ),
    "depends_on": frozenset(
        {
            ("module", "module"),
            ("architecture", "architecture"),
        }
    ),
    "constrains": frozenset(
        {
            ("rule", "flow"),
            ("rule", "module"),
        }
    ),
    "part_of": frozenset({("module", "architecture")}),
    "uses": frozenset(
        {
            ("module", "tech-stack"),
            ("flow", "tech-stack"),
            ("architecture", "tech-stack"),
        }
    ),
}


_KNOWLEDGE_TYPES = ("module", "architecture", "flow", "rule", "tech-stack")


def _object_type(object_id: str) -> str:
    return object_id.split(".", 1)[0]


class CrossTypeRelation(_RelationModel):
    predicate: NonBlankString
    source_id: NonBlankString
    target_id: NonBlankString
    claim_ids: tuple[NonBlankString, ...]

    @field_validator("claim_ids")
    @classmethod
    def require_claims(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("relation claim_ids must not be empty")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_typed_combination(self) -> "CrossTypeRelation":
        allowed = RELATION_RULES.get(self.predicate)
        if allowed is None:
            raise ValueError(
                f"untyped relation predicate: {self.predicate}"
            )
        source_type = _object_type(self.source_id)
        target_type = _object_type(self.target_id)
        if source_type not in _KNOWLEDGE_TYPES:
            raise ValueError(
                f"relation source has an unknown type: {self.source_id}"
            )
        if target_type not in _KNOWLEDGE_TYPES:
            raise ValueError(
                f"relation target has an unknown type: {self.target_id}"
            )
        if (source_type, target_type) not in allowed:
            raise ValueError(
                f"relation predicate {self.predicate} does not allow "
                f"{source_type} -> {target_type}"
            )
        return self


@dataclass(frozen=True)
class ValidatedRelation:
    relation: CrossTypeRelation
    resolved: bool
    unresolved_reason: str | None


@dataclass(frozen=True)
class RelationIndex:
    resolved_relations: int
    unresolved: tuple[ValidatedRelation, ...]
    outbound_index: dict[str, tuple[tuple[str, str], ...]]
    inbound_index: dict[str, tuple[tuple[str, str], ...]]


class RelationRegistry:
    """Validate cross-type relations against known object identities."""

    def __init__(self, *, known_object_ids: frozenset[str]) -> None:
        self._known = frozenset(known_object_ids)

    def validate(self, relation: CrossTypeRelation) -> ValidatedRelation:
        relation = CrossTypeRelation.model_validate(
            relation.model_dump()
        )
        if relation.source_id not in self._known:
            return ValidatedRelation(
                relation=relation,
                resolved=False,
                unresolved_reason="source-missing",
            )
        if relation.target_id not in self._known:
            return ValidatedRelation(
                relation=relation,
                resolved=False,
                unresolved_reason="target-missing",
            )
        return ValidatedRelation(
            relation=relation, resolved=True, unresolved_reason=None
        )

    def validate_all(
        self, relations: list[CrossTypeRelation] | tuple[CrossTypeRelation, ...]
    ) -> RelationIndex:
        validated = [self.validate(relation) for relation in relations]
        resolved = [item for item in validated if item.resolved]
        outbound: dict[str, list[tuple[str, str]]] = {}
        inbound: dict[str, list[tuple[str, str]]] = {}
        for item in resolved:
            edge = (item.relation.predicate, item.relation.source_id)
            outbound.setdefault(item.relation.source_id, []).append(
                (item.relation.predicate, item.relation.target_id)
            )
            inbound.setdefault(item.relation.target_id, []).append(edge)
        return RelationIndex(
            resolved_relations=len(resolved),
            unresolved=tuple(
                item for item in validated if not item.resolved
            ),
            outbound_index={
                key: tuple(sorted(values))
                for key, values in sorted(outbound.items())
            },
            inbound_index={
                key: tuple(sorted(values))
                for key, values in sorted(inbound.items())
            },
        )


__all__ = [
    "CrossTypeRelation",
    "RELATION_RULES",
    "RelationIndex",
    "RelationRegistry",
    "ValidatedRelation",
]
