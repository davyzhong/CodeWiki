from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from knowledge_compiler.contracts.planning import (
    KnowledgePlan,
    PlanRequest,
    PlanTargetSpec,
)
from knowledge_compiler.contracts.evidence import RepositorySurvey
from knowledge_compiler.contracts.repository import PlanTarget


class InsufficientEvidence(ValueError):
    """Raised when survey facts cannot support even one module target."""


# Full refreshes are deliberately bounded so an unexpectedly broad provider
# survey cannot create an unbounded semantic-work queue. The allocation is one
# architecture target, up to 8 modules, up to 7 flows, up to 7 rules, and one
# tech-stack target.
MAX_TARGET_COUNT = 24
_DISCOVERY_LIMITS = {"module": 8, "flow": 7, "rule": 7}
_MAX_EVIDENCE_SEEDS = 3
_FACT_ALIASES = {
    "flow": frozenset(
        {
            "flow",
            "flows",
            "route",
            "routes",
            "entry",
            "entrypoint",
            "entrypoints",
            "interface",
            "interfaces",
        }
    ),
    "rule": frozenset(
        {
            "rule",
            "rules",
            "policy",
            "policies",
            "constraint",
            "constraints",
            "validation",
            "validations",
        }
    ),
}


def plan_one_module(request: PlanRequest, survey: RepositorySurvey) -> KnowledgePlan:
    """Derive one deterministic module target from survey facts only."""

    survey = _validate_survey(survey)
    request = PlanRequest.model_validate(request)
    _validate_correlation(request, survey)

    symbols = sorted(set(survey.symbols))
    if not symbols or not survey.files:
        raise InsufficientEvidence(
            "survey provides no symbols or files to plan a module target"
        )
    communities = sorted(
        (tuple(sorted(community)) for community in survey.graph_communities),
        key=lambda community: (-len(community), community),
    )
    seeds = tuple(communities[0][:3]) if communities else tuple(symbols[:2])
    source_like = [symbol for symbol in seeds if symbol and symbol[0].isupper()]
    if not source_like:
        source_like = seeds[:1]
    if not source_like:
        raise InsufficientEvidence("no usable evidence seeds in the survey")

    topic = " ".join(source_like)
    slug = _module_slug(source_like[0])
    target = PlanTarget(
        id=f"module.{survey.repository_id.split('/')[-1].lower()}.{slug}",
        topic=topic,
        evidence_seeds=tuple(source_like),
    )
    spec = PlanTargetSpec(target=target, priority=1, required=True)
    return KnowledgePlan(
        run_id=request.run_id,
        repository_id=request.repository_id,
        snapshot_id=request.snapshot_id,
        attempt=request.attempt,
        idempotency_key=request.idempotency_key,
        targets=(spec,),
    )


def plan_full_refresh(
    request: PlanRequest, survey: RepositorySurvey
) -> KnowledgePlan:
    """Discover a deterministic, evidence-bounded full-refresh target set."""

    survey = _validate_survey(survey)
    request = PlanRequest.model_validate(request)
    _validate_correlation(request, survey)
    if not survey.files and not survey.symbols:
        raise InsufficientEvidence(
            "survey provides no symbols or files to plan knowledge targets"
        )

    repository_slug = _slug(survey.repository_id.split("/")[-1])
    module_groups = _module_evidence_groups(survey)
    primary_group = module_groups[0]
    primary_slug = _group_slug(primary_group, fallback="module")

    module_specs = _discovered_specs(
        object_type="module",
        repository_slug=repository_slug,
        groups=module_groups,
        priority=2,
    )
    flow_groups = _configuration_groups(survey.configuration_facts, "flow")
    flow_specs = _discovered_specs(
        object_type="flow",
        repository_slug=repository_slug,
        groups=flow_groups or (primary_group,),
        priority=3,
        fixed_suffix=f"{primary_slug}-primary" if not flow_groups else None,
    )
    rule_groups = _configuration_groups(survey.configuration_facts, "rule")
    rule_specs = _discovered_specs(
        object_type="rule",
        repository_slug=repository_slug,
        groups=rule_groups or (primary_group,),
        priority=4,
        fixed_suffix=f"{primary_slug}-behavior" if not rule_groups else None,
    )

    architecture_seeds = tuple(sorted(set(survey.files)))[:_MAX_EVIDENCE_SEEDS]
    if not architecture_seeds:
        architecture_seeds = primary_group
    tech_seeds = _tech_stack_seeds(survey)
    targets = (
        PlanTargetSpec(
            target=PlanTarget(
                id=f"architecture.{repository_slug}.overview",
                type="architecture",
                topic=f"{survey.repository_id} architecture",
                evidence_seeds=architecture_seeds,
            ),
            priority=1,
            required=True,
        ),
        *module_specs,
        *flow_specs,
        *rule_specs,
        PlanTargetSpec(
            target=PlanTarget(
                id=f"tech-stack.{repository_slug}.runtime",
                type="tech-stack",
                topic=f"{survey.repository_id} technology stack",
                evidence_seeds=tech_seeds,
            ),
            priority=5,
            required=True,
        ),
    )
    targets = tuple(sorted(targets, key=lambda spec: (spec.priority, spec.target.id)))
    if len(targets) > MAX_TARGET_COUNT:
        raise AssertionError("planner target allocation exceeded its documented bound")
    return KnowledgePlan(
        run_id=request.run_id,
        repository_id=request.repository_id,
        snapshot_id=request.snapshot_id,
        attempt=request.attempt,
        idempotency_key=request.idempotency_key,
        targets=targets,
    )


def _module_slug(seed_symbol: str) -> str:
    return _slug(seed_symbol, fallback="module")


def _slug(value: str, *, fallback: str = "repository") -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return cleaned[:48].rstrip("-") or fallback


def _validate_survey(survey: RepositorySurvey) -> RepositorySurvey:
    if isinstance(survey, RepositorySurvey):
        # Frozen JSON collections use tuples internally; JSON mode restores the
        # JSON arrays expected when Pydantic revalidates the boundary object.
        survey = survey.model_dump(mode="json")
    return RepositorySurvey.model_validate(survey)


def _validate_correlation(request: PlanRequest, survey: RepositorySurvey) -> None:
    if survey.repository_id != request.repository_id:
        raise ValueError("survey repository does not match the plan request")
    if survey.snapshot_id != request.snapshot_id:
        raise ValueError("survey snapshot does not match the plan request")


def _module_evidence_groups(
    survey: RepositorySurvey,
) -> tuple[tuple[str, ...], ...]:
    groups = _canonical_groups(survey.graph_communities)
    if groups:
        return groups[: _DISCOVERY_LIMITS["module"]]
    symbols = tuple(sorted(set(survey.symbols)))[:_MAX_EVIDENCE_SEEDS]
    if symbols:
        return (symbols,)
    files = tuple(sorted(set(survey.files)))[:_MAX_EVIDENCE_SEEDS]
    if files:
        return (files,)
    raise InsufficientEvidence("no usable evidence seeds in the survey")


def _canonical_groups(
    groups: Sequence[Sequence[str]],
) -> tuple[tuple[str, ...], ...]:
    unique = {
        tuple(sorted(set(item for item in group if item)))[:_MAX_EVIDENCE_SEEDS]
        for group in groups
    }
    unique.discard(())
    return tuple(sorted(unique))


def _configuration_groups(
    facts: Mapping[str, object], object_type: str
) -> tuple[tuple[str, ...], ...]:
    aliases = _FACT_ALIASES[object_type]
    groups: set[tuple[str, ...]] = set()
    for path, value in _configuration_leaves(facts):
        tokens = {
            token
            for part in path
            for token in re.findall(r"[a-z0-9]+", part.lower())
        }
        if not tokens.intersection(aliases):
            continue
        seed = value.strip() if isinstance(value, str) else _fact_seed(path, value)
        if seed:
            groups.add((seed,))
    return tuple(sorted(groups))[: _DISCOVERY_LIMITS[object_type]]


def _configuration_leaves(
    value: object, path: tuple[str, ...] = ()
) -> tuple[tuple[tuple[str, ...], object], ...]:
    leaves: list[tuple[tuple[str, ...], object]] = []
    if isinstance(value, Mapping):
        for key in sorted(value, key=str):
            leaves.extend(_configuration_leaves(value[key], (*path, str(key))))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            leaves.extend(_configuration_leaves(item, path))
    else:
        leaves.append((path, value))
    return tuple(leaves)


def _fact_seed(path: tuple[str, ...], value: object) -> str:
    rendered = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return f"{'.'.join(path)}={rendered}"


def _tech_stack_seeds(survey: RepositorySurvey) -> tuple[str, ...]:
    seeds = set(survey.languages)
    for path, value in _configuration_leaves(survey.configuration_facts):
        if isinstance(value, str):
            rendered = f"{'.'.join(path)}={value}"
        else:
            rendered = _fact_seed(path, value)
        if rendered:
            seeds.add(rendered)
    if not seeds:
        seeds.update(survey.files)
    if not seeds:
        seeds.update(survey.symbols)
    return tuple(sorted(seeds))[:_MAX_EVIDENCE_SEEDS]


def _discovered_specs(
    *,
    object_type: str,
    repository_slug: str,
    groups: Sequence[tuple[str, ...]],
    priority: int,
    fixed_suffix: str | None = None,
) -> tuple[PlanTargetSpec, ...]:
    canonical = _canonical_groups(groups)[: _DISCOVERY_LIMITS[object_type]]
    suffixes = [
        fixed_suffix or _group_slug(group, fallback=object_type) for group in canonical
    ]
    duplicate_suffixes = {suffix for suffix in suffixes if suffixes.count(suffix) > 1}
    specs = []
    for group, suffix in zip(canonical, suffixes, strict=True):
        if suffix in duplicate_suffixes:
            suffix = f"{suffix}-{_group_digest(group)}"
        specs.append(
            PlanTargetSpec(
                target=PlanTarget(
                    id=f"{object_type}.{repository_slug}.{suffix}",
                    type=object_type,
                    topic=" ".join(group),
                    evidence_seeds=group,
                ),
                priority=priority,
                required=True,
            )
        )
    return tuple(specs)


def _group_slug(group: tuple[str, ...], *, fallback: str) -> str:
    source_like = [seed for seed in group if seed and seed[0].isupper()]
    anchor = source_like[0] if source_like else group[0]
    if "/" in anchor:
        anchor = PurePosixPath(anchor).stem
    return _slug(anchor, fallback=fallback)


def _group_digest(group: tuple[str, ...]) -> str:
    payload = json.dumps(group, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


__all__ = [
    "InsufficientEvidence",
    "MAX_TARGET_COUNT",
    "plan_full_refresh",
    "plan_one_module",
]
