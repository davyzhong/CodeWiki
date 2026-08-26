from __future__ import annotations

import hashlib
from typing import Any

from knowledge_compiler.contracts.repository import (
    EvidenceBudget,
    PlanTarget,
    RepositorySnapshot,
)
from knowledge_compiler.orchestrator.queue import QueueError, RunQueue
from knowledge_compiler.orchestrator.contracts import (
    TargetRecord,
    TargetState,
    TerminalResult,
)
from knowledge_compiler.storage import GenerationPublisher, PublicationError
from knowledge_compiler.validation.module import (
    apply_verification_result,
    build_verification_request,
)


DEFAULT_BUDGET = EvidenceBudget(max_items=8, max_characters=4000, max_tokens=512)


class RunnerOutcome:
    def __init__(
        self,
        *,
        status: str,
        generation: str | None,
        published_object_ids: tuple[str, ...],
        diagnostics: tuple[str, ...],
    ) -> None:
        self.status = status
        self.generation = generation
        self.published_object_ids = published_object_ids
        self.diagnostics = diagnostics

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"RunnerOutcome(status={self.status}, "
            f"generation={self.generation}, "
            f"published={self.published_object_ids})"
        )


class RunOrchestrator:
    """Drive every target through the pipeline and own publication.

    The orchestrator — never the worker — moves queue state, decides
    terminal results, and publishes exactly one generation per successful
    run. Any failure leaves the previously committed generation intact.
    """

    def __init__(
        self,
        *,
        queue: RunQueue,
        snapshot: RepositorySnapshot,
        evidence_provider: Any,
        worker: Any,
        output_root: Any,
        run_id: str,
        budget: EvidenceBudget | None = None,
        preserved_items: tuple[tuple[object, object | None], ...] = (),
    ) -> None:
        self.queue = queue
        self.snapshot = snapshot
        self.evidence_provider = evidence_provider
        self.worker = worker
        self.output_root = output_root
        self.run_id = run_id
        self.budget = budget or DEFAULT_BUDGET
        self.preserved_items = preserved_items

    def run(self) -> RunnerOutcome:
        published: list[Any] = []
        packs: dict[str, Any] = {}
        diagnostics: list[str] = []
        any_required_failed = False
        already_published: list[str] = []

        for record in list(self.queue.record().targets):
            if record.published_object_id is not None:
                # A previous invocation published this target; re-entry
                # must not repeat model work or publication.
                already_published.append(record.published_object_id)
                continue
            if record.state is TargetState.DONE:
                if record.required:
                    any_required_failed = True
                continue
            if record.state is TargetState.VERIFIED:
                try:
                    canonical, pack = self.queue.load_verified_artifact(
                        record.target_id
                    )
                except (QueueError, ValueError, OSError) as error:
                    diagnostics.append(
                        f"{record.target_id}: verified artifact unavailable: {error}"
                    )
                    any_required_failed = any_required_failed or record.required
                    continue
                published.append(canonical)
                packs[canonical.id] = pack
                continue
            outcome = self._drive_target(record)
            diagnostics.extend(outcome[1])
            if outcome[0] is not None:
                published.append(outcome[0][0])
                packs[outcome[0][0].id] = outcome[0][1]
            else:
                current = self.queue.target(record.target_id)
                if current.required and current.state is TargetState.DONE:
                    any_required_failed = True

        from knowledge_compiler.human.conflicts import split_overlay_conflicts

        split = split_overlay_conflicts(
            self.output_root,
            tuple((canonical, packs.get(canonical.id)) for canonical in published),
        )
        published = [item[0] for item in split.accepted]
        packs = {item[0].id: item[1] for item in split.accepted}
        for object_id, fields in split.conflicts.items():
            record = self.queue.target(object_id)
            self.queue.replace_record(
                self.queue.record().with_target(
                    record.finish(
                        TerminalResult.CONFLICTED,
                        diagnostics=(
                            "human override evidence changed: "
                            + ", ".join(fields),
                        ),
                    )
                )
            )
            any_required_failed = any_required_failed or record.required
            diagnostics.append(
                f"{object_id}: human override conflict in "
                + ", ".join(fields)
            )

        if already_published and not published:
            self._finalize()
            return RunnerOutcome(
                status="partial" if any_required_failed else "complete",
                generation=None,
                published_object_ids=tuple(sorted(already_published)),
                diagnostics=tuple(diagnostics),
            )
        if not published:
            self._finalize()
            return RunnerOutcome(
                status="partial" if split.conflicts else "failed",
                generation=None,
                published_object_ids=(),
                diagnostics=tuple(diagnostics),
            )

        generation = "gen-" + hashlib.sha256(
            self.run_id.encode("utf-8")
        ).hexdigest()[:32]
        publisher = GenerationPublisher(self.output_root)
        regenerated_ids = [canonical.id for canonical in published]
        preserved_by_id = {
            canonical.id: (canonical, pack)
            for canonical, pack in self.preserved_items + split.preserved
        }
        try:
            publisher.publish_generation(
                generation,
                tuple(
                    (canonical, packs.get(canonical.id))
                    for canonical in published
                )
                + tuple(
                    preserved_by_id[object_id]
                    for object_id in sorted(preserved_by_id)
                    if object_id not in regenerated_ids
                ),
            )
        except PublicationError as error:
            try:
                publisher.recover()
            except PublicationError:
                pass
            self._finalize()
            return RunnerOutcome(
                status="failed",
                generation=None,
                published_object_ids=(),
                diagnostics=tuple(diagnostics + [f"publication failed: {error}"]),
            )
        self._mark_published(
            sorted(set(regenerated_ids + already_published)), generation
        )
        self._finalize()
        return RunnerOutcome(
            status="partial" if any_required_failed else "complete",
            generation=generation,
            published_object_ids=tuple(sorted(regenerated_ids)),
            diagnostics=tuple(diagnostics),
        )

    # -- internals -----------------------------------------------------------

    def _drive_target(self, record: TargetRecord) -> tuple[Any, tuple[str, ...]]:
        target_id = record.target_id
        diagnostics: list[str] = []
        try:
            if record.state is TargetState.QUEUED:
                record = self._to_evidence_ready(record)
            if record.state is TargetState.EVIDENCE_READY:
                pack = self.evidence_provider.build_pack(
                    self.snapshot,
                    PlanTarget(
                        id=target_id,
                        type=record.object_type,
                        topic=record.topic or target_id,
                        evidence_seeds=record.evidence_seeds,
                    ),
                    self.budget,
                )
            else:
                pack = None
            while record.state is TargetState.EVIDENCE_READY:
                lease = self.queue.grant_extraction_lease(target_id, ttl=3600)
                from knowledge_compiler.contracts.semantic import ExtractionRequest

                request = ExtractionRequest.model_validate(
                    {
                        "contract_version": "0.1",
                        "run_id": self.run_id,
                        "target_id": target_id,
                        "operation": "extract",
                        "attempt": lease.attempt,
                        "snapshot_id": self.snapshot.snapshot_id,
                        "idempotency_key": lease.idempotency_key,
                        "evidence_pack": pack,
                    }
                )
                extraction = self.worker.extract(request)
                self.queue.save_extraction_context(
                    target_id, request, extraction
                )
                digest = hashlib.sha256(
                    extraction.model_dump_json().encode("utf-8")
                ).hexdigest()
                record = self.queue.submit_draft(
                    target_id=target_id, lease_token=lease.token,
                    draft_digest="sha256:" + digest,
                )
                break
            while record.state is TargetState.DRAFT_SUBMITTED:
                record = record.transition(TargetState.STRUCTURAL_VALIDATED)
                self.queue.replace_record(
                    self.queue.record().with_target(record)
                )
                record = record.transition(TargetState.SEMANTIC_PENDING)
                self.queue.replace_record(
                    self.queue.record().with_target(record)
                )
                break
            while record.state is TargetState.SEMANTIC_PENDING:
                self.queue.grant_verification_lease(target_id, ttl=3600)
                request, extraction = self.queue.load_extraction_context(
                    target_id
                )
                pack = request.evidence_pack
                verification_request = build_verification_request(
                    request,
                    extraction,
                    self.snapshot.root,
                )
                result = self.worker.verify(verification_request)
                if extraction.draft.type == "module":
                    verified = apply_verification_result(
                        request,
                        extraction,
                        verification_request,
                        result,
                        self.snapshot.root,
                    )
                    canonical = verified.module
                    issue_codes = tuple(
                        issue.code for issue in verified.issues
                    )
                else:
                    from knowledge_compiler.validation.typed import (
                        apply_typed_verification_context,
                    )

                    typed = apply_typed_verification_context(
                        extraction_request=request,
                        extraction=extraction,
                        verification_request=verification_request,
                        verification_result=result,
                        repository_root=self.snapshot.root,
                    )
                    canonical = typed.canonical
                    issue_codes = typed.issues
                if canonical is not None:
                    self.queue.save_verified_artifact(
                        target_id, canonical, pack
                    )
                    record = record.transition(TargetState.VERIFICATION_LEASED)
                    self.queue.replace_record(
                        self.queue.record().with_target(record)
                    )
                    record = record.transition(TargetState.VERIFIED).model_copy(
                        update={"lease": None}
                    )
                    self.queue.replace_record(
                        self.queue.record().with_target(record)
                    )
                    return (canonical, pack), tuple(diagnostics)
                record = record.transition(TargetState.VERIFICATION_LEASED)
                self.queue.replace_record(self.queue.record().with_target(record))
                record = record.finish(
                    TerminalResult.CONFLICTED,
                    diagnostics=tuple(issue_codes)[:20],
                )
                self.queue.replace_record(
                    self.queue.record().with_target(record)
                )
                diagnostics.append(f"{target_id}: verification rejected the draft")
                return None, tuple(diagnostics)
        except (QueueError, ValueError, RuntimeError, OSError) as error:
            record = self.queue.target(target_id)
            finished = record.finish(
                TerminalResult.INVALID, diagnostics=(str(error)[:500],)
            )
            self.queue.replace_record(
                self.queue.record().with_target(finished)
            )
            diagnostics.append(f"{target_id}: {str(error)[:500]}")
            return None, tuple(diagnostics)
        return None, tuple(diagnostics)

    def _to_evidence_ready(self, record: TargetRecord) -> TargetRecord:
        updated = record.transition(TargetState.EVIDENCE_READY)
        self.queue.replace_record(self.queue.record().with_target(updated))
        return updated

    def _mark_published(self, ids: list[str], generation: str) -> None:
        updated_run = self.queue.record()
        for object_id in ids:
            for record in updated_run.targets:
                if record.target_id == object_id:
                    updated_run = updated_run.with_target(
                        record.model_copy(
                            update={"published_object_id": object_id}
                        )
                    )
        self.queue.replace_record(updated_run)

    def _finalize(self) -> None:
        self.queue.replace_record(
            self.queue.record().model_copy(update={"active": False})
        )


__all__ = ["RunOrchestrator", "RunnerOutcome"]
