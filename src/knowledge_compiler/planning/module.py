from __future__ import annotations

from knowledge_compiler.contracts.planning import (
    KnowledgePlan,
    PlanRequest,
    PlanTargetSpec,
)
from knowledge_compiler.contracts.evidence import RepositorySurvey
from knowledge_compiler.contracts.repository import PlanTarget


class InsufficientEvidence(ValueError):
    """Raised when survey facts cannot support even one module target."""


_MODULE_ID_SEEDS = ("checkout", "inventory", "api", "service", "core")


def plan_one_module(request: PlanRequest, survey: RepositorySurvey) -> KnowledgePlan:
    """Derive one deterministic module target from survey facts only."""

    survey = RepositorySurvey.model_validate(survey)
    request = PlanRequest.model_validate(request)
    if survey.repository_id != request.repository_id:
        raise ValueError("survey repository does not match the plan request")
    if survey.snapshot_id != request.snapshot_id:
        raise ValueError("survey snapshot does not match the plan request")

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
    """Plan one evidence-bounded target for every V0.1 knowledge type."""

    module_plan = plan_one_module(request, survey)
    module_spec = module_plan.targets[0]
    module_target = module_spec.target
    repository_slug = _slug(survey.repository_id.split("/")[-1])
    subject_slug = module_target.id.rsplit(".", 1)[-1]
    seeds = module_target.evidence_seeds
    topic = module_target.topic
    definitions = (
        ("architecture", "overview", 1),
        ("module", subject_slug, 2),
        ("flow", f"{subject_slug}-primary", 3),
        ("rule", f"{subject_slug}-behavior", 4),
        ("tech-stack", "runtime", 5),
    )
    targets = tuple(
        PlanTargetSpec(
            target=PlanTarget(
                id=f"{object_type}.{repository_slug}.{name}",
                type=object_type,
                topic=topic,
                evidence_seeds=seeds,
            ),
            priority=priority,
            required=True,
        )
        for object_type, name, priority in definitions
    )
    return KnowledgePlan(
        run_id=request.run_id,
        repository_id=request.repository_id,
        snapshot_id=request.snapshot_id,
        attempt=request.attempt,
        idempotency_key=request.idempotency_key,
        targets=targets,
    )


def _module_slug(seed_symbol: str) -> str:
    cleaned = "".join(
        character if character.isalnum() else "-" for character in seed_symbol.lower()
    ).strip("-")
    return cleaned or "module"


def _slug(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() else "-" for character in value.lower()
    ).strip("-")
    return cleaned or "repository"


__all__ = ["InsufficientEvidence", "plan_full_refresh", "plan_one_module"]
