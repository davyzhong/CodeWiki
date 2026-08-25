from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from knowledge_compiler.contracts.evidence import SHA256_PATTERN
from knowledge_compiler.contracts.repository import NonBlankString


MODULE_ID_PATTERN = re.compile(
    r"^module\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$"
)
# Generic shape for every typed claim; each typed container enforces its
# own type prefix on top of this shared pattern.
CLAIM_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*"
    r"\.claim\.[a-z0-9][a-z0-9_-]*$"
)


from knowledge_compiler.contracts.base import (  # noqa: F401
    ClaimBacked as _ClaimBacked,
    ClaimBackedText,
    Confidence,
    Provenance,
    Relation as _RelationBase,
    Scope,
    Validity,
    ContractModel as _ContractModel,
)


class Responsibility(ClaimBackedText):
    pass


class PublicInterface(_ClaimBacked):
    name: NonBlankString
    description: NonBlankString


class Dependency(_ClaimBacked):
    target: NonBlankString
    description: NonBlankString


class Relation(_RelationBase):
    pass


class DraftClaim(_ContractModel):
    id: NonBlankString
    statement: NonBlankString
    evidence_ids: tuple[str, ...]
    confidence: Confidence
    required: bool = True

    @field_validator("id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        if not CLAIM_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "Claim ID must match <type>.<domain>.<name>.claim.<slug>"
            )
        return value

    @field_validator("evidence_ids")
    @classmethod
    def normalize_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("evidence_ids must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("duplicate Evidence IDs are not allowed")
        if any(not SHA256_PATTERN.fullmatch(item) for item in value):
            raise ValueError("Evidence IDs must be sha256:<64 lowercase hex> hashes")
        return tuple(sorted(value))


class ClaimVerification(_ContractModel):
    status: Literal["supported", "partial", "unsupported", "conflicted"]
    verifier: NonBlankString
    evidence_ids: tuple[str, ...]
    excerpt_hashes: tuple[str, ...]
    verification_request_digest: str

    @model_validator(mode="before")
    @classmethod
    def normalize_evidence_pairs(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        evidence_ids = tuple(data.get("evidence_ids", ()))
        excerpt_hashes = tuple(data.get("excerpt_hashes", ()))
        if len(evidence_ids) == len(excerpt_hashes):
            pairs = sorted(zip(evidence_ids, excerpt_hashes), key=lambda pair: pair[0])
            normalized = dict(data)
            normalized["evidence_ids"] = tuple(pair[0] for pair in pairs)
            normalized["excerpt_hashes"] = tuple(pair[1] for pair in pairs)
            return normalized
        return data

    @field_validator("verification_request_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("verification_request_digest must be a sha256 hash")
        return value

    @model_validator(mode="after")
    def validate_evidence_bindings(self) -> ClaimVerification:
        if not self.evidence_ids:
            raise ValueError("verification evidence_ids must not be empty")
        if len(self.evidence_ids) != len(self.excerpt_hashes):
            raise ValueError("evidence_ids and excerpt_hashes must have equal lengths")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("duplicate Evidence IDs are not allowed")
        if any(not SHA256_PATTERN.fullmatch(item) for item in self.evidence_ids):
            raise ValueError("Evidence IDs must be sha256:<64 lowercase hex> hashes")
        if any(not SHA256_PATTERN.fullmatch(item) for item in self.excerpt_hashes):
            raise ValueError("excerpt_hashes must be sha256:<64 lowercase hex> hashes")
        return self


class Claim(DraftClaim):
    verification: ClaimVerification

    @model_validator(mode="after")
    def verification_must_cover_claim_evidence(self) -> Claim:
        if self.verification.status != "supported":
            raise ValueError("canonical Claim verification must be supported")
        if self.verification.evidence_ids != self.evidence_ids:
            raise ValueError("verification Evidence IDs must match Claim Evidence IDs")
        return self


class _ModulePayload(_ContractModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    type: Literal["module"] = "module"
    title: NonBlankString
    scope: Scope
    summary: ClaimBackedText
    responsibilities: tuple[Responsibility, ...]
    public_interfaces: tuple[PublicInterface, ...]
    dependencies: tuple[Dependency, ...]
    relations: tuple[Relation, ...] = ()
    confidence: Confidence

    _claim_field_names: ClassVar[tuple[str, ...]] = (
        "summary",
        "responsibilities",
        "public_interfaces",
        "dependencies",
        "relations",
    )

    @field_validator("id")
    @classmethod
    def validate_module_id(cls, value: str) -> str:
        if not MODULE_ID_PATTERN.fullmatch(value):
            raise ValueError("module ID must match module.<domain>.<name>")
        return value

    @field_validator("public_interfaces")
    @classmethod
    def normalize_interfaces(
        cls, value: tuple[PublicInterface, ...]
    ) -> tuple[PublicInterface, ...]:
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("duplicate public-interface names are not allowed")
        return tuple(sorted(value, key=lambda item: item.name))

    @field_validator("dependencies")
    @classmethod
    def normalize_dependencies(
        cls, value: tuple[Dependency, ...]
    ) -> tuple[Dependency, ...]:
        targets = [item.target for item in value]
        if len(targets) != len(set(targets)):
            raise ValueError("duplicate dependency targets are not allowed")
        return tuple(sorted(value, key=lambda item: item.target))

    @field_validator("relations")
    @classmethod
    def normalize_relations(cls, value: tuple[Relation, ...]) -> tuple[Relation, ...]:
        keys = [(item.predicate, item.target) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "duplicate relation (predicate, target) keys are not allowed"
            )
        return tuple(sorted(value, key=lambda item: (item.predicate, item.target)))

    def _validate_claim_references(self, known_claim_ids: set[str]) -> None:
        expected_prefix = f"{self.id}.claim."
        foreign = sorted(
            claim_id
            for claim_id in known_claim_ids
            if not claim_id.startswith(expected_prefix)
        )
        if foreign:
            raise ValueError(
                "Claims must belong to the containing Module: " + ", ".join(foreign)
            )
        referenced: list[str] = list(self.summary.claim_ids)
        for field_name in self._claim_field_names[1:]:
            for item in getattr(self, field_name):
                referenced.extend(item.claim_ids)
        unknown = sorted(set(referenced) - known_claim_ids)
        if unknown:
            raise ValueError(f"unknown Claim references: {', '.join(unknown)}")


KNOWLEDGE_OBJECT_ID_PATTERN = re.compile(
    r"^(module|architecture|flow|rule|tech-stack)"
    r"\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$"
)
FLOW_ID_PATTERN = re.compile(
    r"^flow\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$"
)
FLOW_CLAIM_PATTERN = re.compile(
    r"^flow\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*"
    r"\.claim\.[a-z0-9][a-z0-9_-]*$"
)


class FlowTrigger(_ClaimBacked):
    description: NonBlankString


class FlowStep(_ClaimBacked):
    step_id: NonBlankString
    order: int = Field(strict=True, ge=1)
    description: NonBlankString
    participants: tuple[NonBlankString, ...]

    @field_validator("participants")
    @classmethod
    def normalize_participants(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if not value:
            raise ValueError("flow step participants must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("duplicate flow step participants are not allowed")
        return tuple(sorted(value))


class FlowFailurePath(_ClaimBacked):
    condition: NonBlankString
    handling: NonBlankString


class FlowKnowledge(_ContractModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    type: Literal["flow"] = "flow"
    title: NonBlankString
    scope: Scope
    summary: ClaimBackedText
    trigger: FlowTrigger
    steps: tuple[FlowStep, ...]
    failure_paths: tuple[FlowFailurePath, ...] = ()
    claims: tuple[Claim, ...]
    provenance: Provenance
    validity: Validity

    @field_validator("id")
    @classmethod
    def validate_flow_id(cls, value: str) -> str:
        if not FLOW_ID_PATTERN.fullmatch(value):
            raise ValueError("flow ID must match flow.<domain>.<name>")
        return value

    @field_validator("steps")
    @classmethod
    def normalize_steps(cls, value: tuple[FlowStep, ...]) -> tuple[FlowStep, ...]:
        ids = [step.step_id for step in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate flow step ids are not allowed")
        if not value:
            raise ValueError("flow requires at least one step")
        ordered = sorted(value, key=lambda step: step.order)
        expected = 1
        for step in ordered:
            if step.order != expected:
                raise ValueError(
                    f"flow step order must be contiguous from 1; got "
                    f"{step.order} where {expected} was expected"
                )
            expected += 1
        return tuple(ordered)

    @field_validator("failure_paths")
    @classmethod
    def normalize_failure_paths(
        cls, value: tuple[FlowFailurePath, ...]
    ) -> tuple[FlowFailurePath, ...]:
        keys = [(item.condition, item.handling) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate failure paths are not allowed")
        return tuple(
            sorted(value, key=lambda item: (item.condition, item.handling))
        )

    @field_validator("claims")
    @classmethod
    def normalize_flow_claims(cls, value: tuple[Claim, ...]) -> tuple[Claim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        for claim in value:
            if not FLOW_CLAIM_PATTERN.fullmatch(claim.id):
                raise ValueError(
                    "Claim ID must match flow.<domain>.<name>.claim.<slug>"
                )
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_flow_references(self) -> FlowKnowledge:
        referenced: list[str] = list(self.summary.claim_ids)
        referenced.extend(self.trigger.claim_ids)
        for collection in (self.steps, self.failure_paths):
            for item in collection:
                referenced.extend(item.claim_ids)
        known = {claim.id for claim in self.claims}
        unknown = sorted(set(referenced) - known)
        if unknown:
            raise ValueError(f"unknown Claim references: {', '.join(unknown)}")
        if (
            self.validity.status == "verified"
            and self.validity.verified_commit != self.scope.commit
        ):
            raise ValueError(
                "verified validity verified_commit must match the scope commit"
            )
        return self


RULE_ID_PATTERN = re.compile(
    r"^rule\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$"
)
RULE_CLAIM_PATTERN = re.compile(
    r"^rule\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*"
    r"\.claim\.[a-z0-9][a-z0-9_-]*$"
)


class RuleConstraint(_ClaimBacked):
    description: NonBlankString


class RuleException(_ClaimBacked):
    description: NonBlankString


class RuleApplicability(_ClaimBacked):
    paths: tuple[str, ...]

    @field_validator("paths")
    @classmethod
    def normalize_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("rule applicability requires at least one path")
        for path in value:
            parsed = PurePosixPath(path) if path and "/" in path else None
            if (
                not path
                or path.startswith("/")
                or (parsed is not None and ".." in parsed.parts)
            ):
                raise ValueError(
                    "rule applicability paths must be safe relative paths"
                )
        if len(value) != len(set(value)):
            raise ValueError("duplicate applicability paths are not allowed")
        return tuple(sorted(value))


class RuleKnowledge(_ContractModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    type: Literal["rule"] = "rule"
    title: NonBlankString
    scope: Scope
    summary: ClaimBackedText
    statement: ClaimBackedText
    severity: Literal["must", "should", "may"]
    applicability: RuleApplicability
    constraints: tuple[RuleConstraint, ...] = ()
    exceptions: tuple[RuleException, ...] = ()
    related_objects: tuple[str, ...] = ()
    claims: tuple[Claim, ...]
    provenance: Provenance
    validity: Validity

    @field_validator("id")
    @classmethod
    def validate_rule_id(cls, value: str) -> str:
        if not RULE_ID_PATTERN.fullmatch(value):
            raise ValueError("rule ID must match rule.<domain>.<name>")
        return value

    @field_validator("related_objects")
    @classmethod
    def normalize_related(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate related objects are not allowed")
        for target in value:
            if not KNOWLEDGE_OBJECT_ID_PATTERN.fullmatch(target):
                raise ValueError(
                    f"related object id has an unsafe shape: {target}"
                )
        return tuple(sorted(value))

    @field_validator("constraints")
    @classmethod
    def normalize_constraints(
        cls, value: tuple[RuleConstraint, ...]
    ) -> tuple[RuleConstraint, ...]:
        descriptions = [item.description for item in value]
        if len(descriptions) != len(set(descriptions)):
            raise ValueError("duplicate rule constraints are not allowed")
        return tuple(sorted(value, key=lambda item: item.description))

    @field_validator("exceptions")
    @classmethod
    def normalize_exceptions(
        cls, value: tuple[RuleException, ...]
    ) -> tuple[RuleException, ...]:
        descriptions = [item.description for item in value]
        if len(descriptions) != len(set(descriptions)):
            raise ValueError("duplicate rule exceptions are not allowed")
        return tuple(sorted(value, key=lambda item: item.description))

    @field_validator("claims")
    @classmethod
    def normalize_rule_claims(cls, value: tuple[Claim, ...]) -> tuple[Claim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        for claim in value:
            if not RULE_CLAIM_PATTERN.fullmatch(claim.id):
                raise ValueError(
                    "Claim ID must match rule.<domain>.<name>.claim.<slug>"
                )
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_rule_references(self) -> RuleKnowledge:
        referenced: list[str] = list(self.summary.claim_ids)
        referenced.extend(self.statement.claim_ids)
        referenced.extend(self.applicability.claim_ids)
        for collection in (self.constraints, self.exceptions):
            for item in collection:
                referenced.extend(item.claim_ids)
        known = {claim.id for claim in self.claims}
        unknown = sorted(set(referenced) - known)
        if unknown:
            raise ValueError(f"unknown Claim references: {', '.join(unknown)}")
        if (
            self.validity.status == "verified"
            and self.validity.verified_commit != self.scope.commit
        ):
            raise ValueError(
                "verified validity verified_commit must match the scope commit"
            )
        return self


TECH_STACK_ID_PATTERN = re.compile(
    r"^tech-stack\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$"
)
TECH_STACK_CLAIM_PATTERN = re.compile(
    r"^tech-stack\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*"
    r"\.claim\.[a-z0-9][a-z0-9_-]*$"
)
_VERSION_PATTERN = re.compile(
    r"^(unknown|\d+[0-9A-Za-z.+-]*(?:/[0-9A-Za-z.+-]+)*)$"
)


class TechEntry(_ClaimBacked):
    name: NonBlankString
    category: NonBlankString
    version: str
    scope: NonBlankString

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _VERSION_PATTERN.fullmatch(value):
            raise ValueError(
                "version must be an explicit identifier or the literal "
                "'unknown'; never a guess"
            )
        return value


class TechConfiguration(_ClaimBacked):
    path: str
    description: NonBlankString

    @field_validator("path")
    @classmethod
    def validate_config_path(cls, value: str) -> str:
        parsed = PurePosixPath(value)
        if (
            not value
            or value.startswith("/")
            or ".." in parsed.parts
            or parsed.as_posix() != value
        ):
            raise ValueError(
                "configuration path must be a safe relative POSIX path"
            )
        return value


class TechStackKnowledge(_ContractModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    type: Literal["tech-stack"] = "tech-stack"
    title: NonBlankString
    scope: Scope
    summary: ClaimBackedText
    entries: tuple[TechEntry, ...]
    configurations: tuple[TechConfiguration, ...] = ()
    claims: tuple[Claim, ...]
    provenance: Provenance
    validity: Validity

    @field_validator("id")
    @classmethod
    def validate_tech_stack_id(cls, value: str) -> str:
        if not TECH_STACK_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "tech-stack ID must match tech-stack.<domain>.<name>"
            )
        return value

    @field_validator("entries")
    @classmethod
    def normalize_entries(
        cls, value: tuple[TechEntry, ...]
    ) -> tuple[TechEntry, ...]:
        names = [entry.name for entry in value]
        if len(names) != len(set(names)):
            raise ValueError("duplicate technology aliases are not allowed")
        if not value:
            raise ValueError("tech-stack requires at least one entry")
        return tuple(sorted(value, key=lambda entry: (entry.name, entry.category)))

    @field_validator("configurations")
    @classmethod
    def normalize_configurations(
        cls, value: tuple[TechConfiguration, ...]
    ) -> tuple[TechConfiguration, ...]:
        paths = [item.path for item in value]
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate configuration paths are not allowed")
        return tuple(sorted(value, key=lambda item: item.path))

    @field_validator("claims")
    @classmethod
    def normalize_tech_claims(cls, value: tuple[Claim, ...]) -> tuple[Claim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        for claim in value:
            if not TECH_STACK_CLAIM_PATTERN.fullmatch(claim.id):
                raise ValueError(
                    "Claim ID must match tech-stack.<domain>.<name>.claim.<slug>"
                )
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_tech_references(self) -> TechStackKnowledge:
        referenced: list[str] = list(self.summary.claim_ids)
        for collection in (self.entries, self.configurations):
            for item in collection:
                referenced.extend(item.claim_ids)
        known = {claim.id for claim in self.claims}
        unknown = sorted(set(referenced) - known)
        if unknown:
            raise ValueError(f"unknown Claim references: {', '.join(unknown)}")
        if (
            self.validity.status == "verified"
            and self.validity.verified_commit != self.scope.commit
        ):
            raise ValueError(
                "verified validity verified_commit must match the scope commit"
            )
        return self


class DraftModuleKnowledge(_ModulePayload):
    claims: tuple[DraftClaim, ...]

    @field_validator("claims")
    @classmethod
    def normalize_claims(cls, value: tuple[DraftClaim, ...]) -> tuple[DraftClaim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_claim_references(self) -> DraftModuleKnowledge:
        self._validate_claim_references({claim.id for claim in self.claims})
        return self


try:  # local import to avoid a cycle: semantic imports knowledge
    from knowledge_compiler.contracts.semantic import DraftKnowledge
except ImportError:  # pragma: no cover
    DraftKnowledge = DraftModuleKnowledge

ARCHITECTURE_ID_PATTERN = re.compile(
    r"^architecture\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$"
)
ARCHITECTURE_CLAIM_PATTERN = re.compile(
    r"^architecture\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*"
    r"\.claim\.[a-z0-9][a-z0-9_-]*$"
)


class ArchitectureComponent(_ClaimBacked):
    name: NonBlankString
    responsibility: NonBlankString


class ArchitectureBoundary(_ClaimBacked):
    name: NonBlankString
    description: NonBlankString


class ArchitectureRelationship(_ClaimBacked):
    predicate: NonBlankString
    source: NonBlankString
    target: NonBlankString


class ArchitectureKnowledge(_ContractModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    type: Literal["architecture"] = "architecture"
    title: NonBlankString
    scope: Scope
    summary: ClaimBackedText
    components: tuple[ArchitectureComponent, ...]
    boundaries: tuple[ArchitectureBoundary, ...]
    relationships: tuple[ArchitectureRelationship, ...] = ()
    claims: tuple[Claim, ...]
    provenance: Provenance
    validity: Validity

    @field_validator("id")
    @classmethod
    def validate_architecture_id(cls, value: str) -> str:
        if not ARCHITECTURE_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "architecture ID must match architecture.<domain>.<name>"
            )
        return value

    @field_validator("components")
    @classmethod
    def normalize_components(
        cls, value: tuple[ArchitectureComponent, ...]
    ) -> tuple[ArchitectureComponent, ...]:
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("duplicate component names are not allowed")
        if not value:
            raise ValueError("architecture requires at least one component")
        return tuple(sorted(value, key=lambda item: item.name))

    @field_validator("boundaries")
    @classmethod
    def normalize_boundaries(
        cls, value: tuple[ArchitectureBoundary, ...]
    ) -> tuple[ArchitectureBoundary, ...]:
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("duplicate boundary names are not allowed")
        return tuple(sorted(value, key=lambda item: item.name))

    @field_validator("relationships")
    @classmethod
    def normalize_relationships(
        cls, value: tuple[ArchitectureRelationship, ...]
    ) -> tuple[ArchitectureRelationship, ...]:
        keys = [
            (item.predicate, item.source, item.target) for item in value
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "duplicate relationship keys are not allowed"
            )
        return tuple(
            sorted(
                value,
                key=lambda item: (item.predicate, item.source, item.target),
            )
        )

    @field_validator("claims")
    @classmethod
    def normalize_claims(cls, value: tuple[Claim, ...]) -> tuple[Claim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        for claim in value:
            if not ARCHITECTURE_CLAIM_PATTERN.fullmatch(claim.id):
                raise ValueError(
                    "Claim ID must match architecture.<domain>.<name>.claim.<slug>"
                )
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_references(self) -> ArchitectureKnowledge:
        referenced: list[str] = list(self.summary.claim_ids)
        for field in ("components", "boundaries", "relationships"):
            for item in getattr(self, field):
                referenced.extend(item.claim_ids)
        known = {claim.id for claim in self.claims}
        unknown = sorted(set(referenced) - known)
        if unknown:
            raise ValueError(f"unknown Claim references: {', '.join(unknown)}")
        component_names = {component.name for component in self.components}
        for relationship in self.relationships:
            if (
                relationship.source not in component_names
                or relationship.target not in component_names
            ):
                raise ValueError(
                    "relationship references an unknown component: "
                    f"{relationship.source} -> {relationship.target}"
                )
        if (
            self.validity.status == "verified"
            and self.validity.verified_commit != self.scope.commit
        ):
            raise ValueError(
                "verified validity verified_commit must match the scope commit"
            )
        return self




class ExtractionResult(_ContractModel):
    contract_version: Literal["0.1"]
    run_id: NonBlankString
    target_id: NonBlankString
    operation: Literal["extract"]
    attempt: int = Field(strict=True, gt=0)
    snapshot_id: NonBlankString
    idempotency_key: NonBlankString
    draft: DraftKnowledge
    provenance: Provenance


class ModuleKnowledge(_ModulePayload):
    claims: tuple[Claim, ...]
    provenance: Provenance
    validity: Validity

    @field_validator("claims")
    @classmethod
    def normalize_claims(cls, value: tuple[Claim, ...]) -> tuple[Claim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        return tuple(sorted(value, key=lambda claim: claim.id))

    @model_validator(mode="after")
    def validate_canonical_claims(self) -> ModuleKnowledge:
        self._validate_claim_references({claim.id for claim in self.claims})
        if (
            self.validity.status == "verified"
            and self.validity.verified_commit != self.scope.commit
        ):
            raise ValueError(
                "verified validity verified_commit must match the scope commit"
            )
        return self


class _TypedDraftBase:
    """Shared draft behavior: unverified claims, no validity."""

    pass


def _draft_claims_validator(pattern):
    def validate(value: tuple[DraftClaim, ...]) -> tuple[DraftClaim, ...]:
        ids = [claim.id for claim in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Claim IDs are not allowed")
        for claim in value:
            if not pattern.fullmatch(claim.id):
                raise ValueError(
                    "Claim ID must match <type>.<domain>.<name>.claim.<slug>"
                )
        return tuple(sorted(value, key=lambda claim: claim.id))

    return validate


class DraftArchitectureKnowledge(_TypedDraftBase, ArchitectureKnowledge):
    claims: tuple[DraftClaim, ...]
    validity: None = None

    _draft_claims = field_validator("claims")(
        _draft_claims_validator(ARCHITECTURE_CLAIM_PATTERN)
    )

    @model_validator(mode="after")
    def drop_validity_checks(self) -> "DraftArchitectureKnowledge":
        object.__getattribute__(self, "claims")
        return self


class DraftFlowKnowledge(_TypedDraftBase, FlowKnowledge):
    claims: tuple[DraftClaim, ...]
    validity: None = None

    _draft_claims = field_validator("claims")(
        _draft_claims_validator(FLOW_CLAIM_PATTERN)
    )


class DraftRuleKnowledge(_TypedDraftBase, RuleKnowledge):
    claims: tuple[DraftClaim, ...]
    validity: None = None

    _draft_claims = field_validator("claims")(
        _draft_claims_validator(RULE_CLAIM_PATTERN)
    )


class DraftTechStackKnowledge(_TypedDraftBase, TechStackKnowledge):
    claims: tuple[DraftClaim, ...]
    validity: None = None

    _draft_claims = field_validator("claims")(
        _draft_claims_validator(TECH_STACK_CLAIM_PATTERN)
    )



__all__ = [
    "DraftArchitectureKnowledge",
    "DraftFlowKnowledge",
    "DraftRuleKnowledge",
    "DraftTechStackKnowledge",
    "TechConfiguration",
    "TechEntry",
    "TechStackKnowledge",
    "RuleApplicability",
    "RuleConstraint",
    "RuleException",
    "RuleKnowledge",
    "FlowFailurePath",
    "FlowKnowledge",
    "FlowStep",
    "FlowTrigger",
    "ArchitectureBoundary",
    "ArchitectureComponent",
    "ArchitectureKnowledge",
    "ArchitectureRelationship",
    "Claim",
    "ClaimBackedText",
    "ClaimVerification",
    "Confidence",
    "Dependency",
    "DraftClaim",
    "DraftModuleKnowledge",
    "ExtractionResult",
    "ModuleKnowledge",
    "Provenance",
    "PublicInterface",
    "Relation",
    "Responsibility",
    "Scope",
    "Validity",
]
