from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge_compiler.contracts.knowledge import ExtractionResult
from knowledge_compiler.contracts.planning import PlanRequest
from knowledge_compiler.contracts.repository import EvidenceBudget, PlanTarget
from knowledge_compiler.planning.module import plan_one_module
from knowledge_compiler.preflight import PreflightFailure, run_preflight
from knowledge_compiler.repository.local_git import (
    LocalGitRepositoryProvider,
    RepositoryResolutionError,
)
from knowledge_compiler.storage import GenerationPublisher, PublicationError
from knowledge_compiler.validation.module import (
    apply_verification_result,
    build_verification_request,
)
from knowledge_compiler.workers.litellm_worker import (
    WorkerOutputError,
    WorkerTransportError,
)


DEFAULT_BUDGET = EvidenceBudget(max_items=8, max_characters=4000, max_tokens=512)


@dataclass(frozen=True)
class RealSliceSuccess:
    generation: str
    object_id: str
    canonical_path: Path
    card_path: Path
    wiki_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class RealSliceFailure:
    reason: str
    message: str


def run_real_module_slice(
    *,
    repository_root: Path,
    evidence_provider: Any,
    worker: Any,
    output_root: Path,
    config_path: Path | None = None,
    snapshot: Any | None = None,
    run_id: str = "m2-real-run-001",
    fault_injector: Callable[[str], None] | None = None,
) -> RealSliceSuccess | RealSliceFailure:
    """Non-orchestrated M2 harness: preflight through M1 publication.

    The evidence provider and semantic worker are injected, so the fixture
    path runs deterministically while a live caller supplies the real
    CodeWiki adapter and LiteLLM worker. An optional pre-resolved snapshot
    lets fixture tests bind the captured CodeWiki world.
    """

    try:
        run_preflight(repository_root, config_path=config_path)
        if snapshot is None:
            snapshot = LocalGitRepositoryProvider().resolve(repository_root)
        evidence_provider.ensure_index(snapshot)
        survey = evidence_provider.inspect(snapshot)
        plan_request = PlanRequest.model_validate(
            {
                "run_id": run_id,
                "repository_id": snapshot.repository_id,
                "snapshot_id": snapshot.snapshot_id,
                "attempt": 1,
                "idempotency_key": f"{run_id}:plan:1:{snapshot.snapshot_id}",
            }
        )
        plan = plan_one_module(plan_request, survey)
        target: PlanTarget = plan.targets[0].target
        pack = evidence_provider.build_pack(snapshot, target, DEFAULT_BUDGET)
        request = _extraction_request(run_id, target, pack)
        extraction = worker.extract(request)
        if not isinstance(extraction, ExtractionResult):
            return RealSliceFailure(
                "extraction.contract", "worker returned no contract result"
            )
        verification_request = build_verification_request(
            request, extraction, pack.repository.root
        )
        verification = worker.verify(verification_request)
        verified = apply_verification_result(
            request,
            extraction,
            verification_request,
            verification,
            pack.repository.root,
        )
        if not verified.is_valid or verified.module is None:
            return RealSliceFailure(
                "verification",
                "semantic verification rejected the draft",
            )
        publisher = GenerationPublisher(output_root, fault_injector=fault_injector)
        generation = "gen-" + hashlib.sha256(
            f"{run_id}:{target.id}:{snapshot.snapshot_id}:1".encode("utf-8")
        ).hexdigest()[:32]
        try:
            published = publisher.publish(generation, verified.module, pack)
        except PublicationError:
            try:
                publisher.recover()
            except PublicationError:
                pass
            raise
        return RealSliceSuccess(
            generation=published.generation,
            object_id=verified.module.id,
            canonical_path=published.canonical_path,
            card_path=published.card_path,
            wiki_path=published.wiki_path,
            manifest_path=published.manifest_path,
        )
    except PreflightFailure as error:
        return RealSliceFailure("preflight", str(error))
    except RepositoryResolutionError as error:
        return RealSliceFailure("repository", str(error))
    except (WorkerTransportError, WorkerOutputError) as error:
        return RealSliceFailure("model", str(error)[:2000])
    except ValueError as error:
        return RealSliceFailure("validation", str(error)[:2000])
    except PublicationError as error:
        return RealSliceFailure("publication", str(error))
    except OSError as error:
        return RealSliceFailure("infrastructure", str(error)[:2000])


def _extraction_request(run_id: str, target: PlanTarget, pack: Any):
    from knowledge_compiler.contracts.semantic import ExtractionRequest

    return ExtractionRequest.model_validate(
        {
            "contract_version": "0.1",
            "run_id": run_id,
            "target_id": target.id,
            "operation": "extract",
            "attempt": 1,
            "snapshot_id": pack.repository.snapshot_id,
            "idempotency_key": (
                f"{run_id}:{target.id}:extract:1:{pack.repository.snapshot_id}"
            ),
            "evidence_pack": pack,
        }
    )


__all__ = [
    "RealSliceFailure",
    "RealSliceSuccess",
    "run_real_module_slice",
]
