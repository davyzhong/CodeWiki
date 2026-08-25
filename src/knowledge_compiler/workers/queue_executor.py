from __future__ import annotations

from typing import Any

from knowledge_compiler.orchestrator.runner import RunOrchestrator, RunnerOutcome


class QueueExecutor:
    """Built-in transport: drive the persisted queue in-process.

    Re-invoking execute_all over a run is always safe: completed targets
    are skipped, interrupted work resumes from its persisted state, and
    the underlying orchestrator owns retries and publication.
    """

    def __init__(
        self,
        *,
        orchestrator: RunOrchestrator,
        evidence_provider: Any,
        worker: Any,
    ) -> None:
        self._orchestrator = orchestrator
        self._evidence_provider = evidence_provider
        self._worker = worker

    @classmethod
    def from_queue(
        cls,
        *,
        queue,
        snapshot,
        evidence_provider,
        worker,
        output_root,
        run_id: str,
    ) -> "QueueExecutor":
        return cls(
            orchestrator=RunOrchestrator(
                queue=queue,
                snapshot=snapshot,
                evidence_provider=evidence_provider,
                worker=worker,
                output_root=output_root,
                run_id=run_id,
            ),
            evidence_provider=evidence_provider,
            worker=worker,
        )

    def execute_all(self) -> RunnerOutcome:
        return self._orchestrator.run()


__all__ = ["QueueExecutor"]
