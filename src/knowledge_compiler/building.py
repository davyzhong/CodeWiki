from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from knowledge_compiler.contracts.planning import PlanRequest
from knowledge_compiler.contracts.repository import (
    EvidenceBudget,
    PlanTarget,
    RepositorySnapshot,
)
from knowledge_compiler.config import KnowledgeConfig, WorkerProfiles
from knowledge_compiler.orchestrator.contracts import RunRecord, TargetState
from knowledge_compiler.orchestrator.queue import RunQueue
from knowledge_compiler.orchestrator.runner import RunOrchestrator
from knowledge_compiler.orchestrator.store import RunStore, RunStoreError
from knowledge_compiler.planning.module import plan_full_refresh
from knowledge_compiler.repository.local_git import LocalGitRepositoryProvider


DEFAULT_BUDGET = EvidenceBudget(max_items=8, max_characters=4000, max_tokens=512)


@dataclass(frozen=True)
class PrimaryBuildOutcome:
    status: Literal["complete", "partial", "failed"]
    generation: str | None
    published_object_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]
    run_id: str


class BuildConfigurationError(ValueError):
    """Raised when user-level runtime configuration cannot resolve a worker."""


class _WallClock:
    def __call__(self) -> int:
        return int(time.time())


def run_primary_build(
    *,
    repository_root: Path,
    executor: Literal["llm", "agent"],
    evidence_provider: Any,
    worker: Any | None = None,
    snapshot: RepositorySnapshot | None = None,
    run_id: str | None = None,
    budget: EvidenceBudget | None = None,
    planner: Callable[[PlanRequest, Any], Any] = plan_full_refresh,
) -> PrimaryBuildOutcome:
    """Run or prepare the production build pipeline over real provider contracts."""

    root = Path(repository_root).resolve()
    resolved = snapshot or LocalGitRepositoryProvider().resolve(root)
    selected_budget = budget or DEFAULT_BUDGET
    store_root = root / ".knowledge/state/runs"
    active = RunStore(store_root).active_run()
    if active is not None:
        if run_id is not None and active.run_id != run_id:
            raise RunStoreError(
                f"active run {active.run_id} must finish before {run_id}"
            )
        if (
            active.repository_id != resolved.repository_id
            or active.snapshot_id != resolved.snapshot_id
            or active.executor != executor
        ):
            raise RunStoreError(
                "active run repository, snapshot, or executor does not match"
            )
        queue = RunQueue(
            store_root=store_root,
            run=active,
            clock=_WallClock(),
        )
        evidence_provider.ensure_index(resolved)
        if executor == "agent":
            _prepare_agent_evidence(
                queue, resolved, evidence_provider, selected_budget
            )
            return _agent_outcome(active.run_id, resumed=True)
        queue.expire_leases()
        if any(record.lease is not None for record in queue.record().targets):
            return PrimaryBuildOutcome(
                status="partial",
                generation=None,
                published_object_ids=(),
                diagnostics=("active model lease is still in progress",),
                run_id=active.run_id,
            )
        return _run_llm_queue(
            queue=queue,
            snapshot=resolved,
            evidence_provider=evidence_provider,
            worker=worker,
            root=root,
            run_id=active.run_id,
            budget=selected_budget,
        )

    actual_run_id = run_id or _run_id(resolved)

    evidence_provider.ensure_index(resolved)
    survey = evidence_provider.inspect(resolved)
    request = PlanRequest(
        run_id=actual_run_id,
        repository_id=resolved.repository_id,
        snapshot_id=resolved.snapshot_id,
        attempt=1,
        idempotency_key=(
            f"{actual_run_id}:plan:1:{resolved.snapshot_id}"
        ),
    )
    plan = planner(request, survey)
    initial_state = "queued" if executor == "llm" else "evidence_ready"
    run = RunRecord.model_validate(
        {
            "run_id": actual_run_id,
            "repository_id": resolved.repository_id,
            "snapshot_id": resolved.snapshot_id,
            "executor": executor,
            "active": True,
            "targets": tuple(
                {
                    "target_id": spec.target.id,
                    "object_type": spec.target.type,
                    "topic": spec.target.topic,
                    "evidence_seeds": spec.target.evidence_seeds,
                    "state": initial_state,
                    "attempt": 1,
                    "repair_attempts": 0,
                    "required": spec.required,
                    "priority": spec.priority,
                    "result": None,
                    "published_object_id": None,
                    "request_digest": _target_digest(spec.target),
                    "result_digest": None,
                    "diagnostics": (),
                    "lease": None,
                }
                for spec in plan.targets
            ),
        }
    )
    queue = RunQueue(
        store_root=store_root,
        run=run,
        clock=_WallClock(),
    )
    queue.save_plan(plan)

    if executor == "agent":
        _prepare_agent_evidence(
            queue, resolved, evidence_provider, selected_budget
        )
        return _agent_outcome(actual_run_id, resumed=False)

    return _run_llm_queue(
        queue=queue,
        snapshot=resolved,
        evidence_provider=evidence_provider,
        worker=worker,
        root=root,
        run_id=actual_run_id,
        budget=selected_budget,
    )


def _run_llm_queue(
    *,
    queue: RunQueue,
    snapshot: RepositorySnapshot,
    evidence_provider: Any,
    worker: Any | None,
    root: Path,
    run_id: str,
    budget: EvidenceBudget,
) -> PrimaryBuildOutcome:
    if worker is None:
        raise ValueError("llm executor requires a semantic worker")
    outcome = RunOrchestrator(
        queue=queue,
        snapshot=snapshot,
        evidence_provider=evidence_provider,
        worker=worker,
        output_root=root,
        run_id=run_id,
        budget=budget,
    ).run()
    return PrimaryBuildOutcome(
        status=outcome.status,
        generation=outcome.generation,
        published_object_ids=outcome.published_object_ids,
        diagnostics=outcome.diagnostics,
        run_id=run_id,
    )


def _prepare_agent_evidence(
    queue: RunQueue,
    snapshot: RepositorySnapshot,
    evidence_provider: Any,
    budget: EvidenceBudget,
) -> None:
    for record in queue.record().targets:
        if record.state is not TargetState.EVIDENCE_READY:
            continue
        try:
            queue.load_evidence_pack(record.target_id)
            continue
        except (RunStoreError, OSError, ValueError):
            pass
        target = PlanTarget(
            id=record.target_id,
            type=record.object_type,
            topic=record.topic or record.target_id,
            evidence_seeds=record.evidence_seeds,
        )
        pack = evidence_provider.build_pack(snapshot, target, budget)
        queue.save_evidence_pack(record.target_id, pack)


def _agent_outcome(run_id: str, *, resumed: bool) -> PrimaryBuildOutcome:
    message = (
        "active agent queue resumed; semantic work is pending"
        if resumed
        else "agent queue prepared; semantic work is pending"
    )
    return PrimaryBuildOutcome(
        status="partial",
        generation=None,
        published_object_ids=(),
        diagnostics=(message,),
        run_id=run_id,
    )


def run_configured_build(
    *,
    repository_root: Path,
    executor: Literal["llm", "agent"],
    config: KnowledgeConfig,
) -> PrimaryBuildOutcome:
    """Construct production adapters and enter the shared primary pipeline."""

    from knowledge_compiler.providers.codewiki import CodeWikiEvidenceProvider
    from knowledge_compiler.providers.codewiki_cli import CodewikiRunner

    root = Path(repository_root).resolve()
    worker = (
        create_llm_worker(config.worker_profiles)
        if executor == "llm"
        else None
    )
    provider = CodeWikiEvidenceProvider(
        CodewikiRunner(), repository_root=root
    )
    return run_primary_build(
        repository_root=root,
        executor=executor,
        evidence_provider=provider,
        worker=worker,
    )


def create_llm_worker(profiles: WorkerProfiles) -> Any:
    """Resolve repository profile names through user-level environment config."""

    from knowledge_compiler.workers.litellm_worker import LiteLLMWorker

    extraction_model = os.environ.get("KNOWLEDGE_EXTRACTION_MODEL")
    if not extraction_model:
        raise BuildConfigurationError(
            "KNOWLEDGE_EXTRACTION_MODEL is not configured for profile "
            f"{profiles.extraction_profile!r}"
        )
    verification_model = os.environ.get("KNOWLEDGE_VALIDATION_MODEL")
    if profiles.validation_profile and not verification_model:
        raise BuildConfigurationError(
            "KNOWLEDGE_VALIDATION_MODEL is not configured for profile "
            f"{profiles.validation_profile!r}"
        )

    def transport(*, system: str, user: str, model: str) -> str:
        import litellm

        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    return LiteLLMWorker(
        transport=transport,
        extraction_model=extraction_model,
        verification_model=verification_model,
    )


def _run_id(snapshot: RepositorySnapshot) -> str:
    digest = hashlib.sha256(
        f"build:{snapshot.snapshot_id}:{time.time_ns()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"build-{digest}"


def _target_digest(target: Any) -> str:
    payload = target.model_dump_json().encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


__all__ = [
    "BuildConfigurationError",
    "PrimaryBuildOutcome",
    "create_llm_worker",
    "run_configured_build",
    "run_primary_build",
]
