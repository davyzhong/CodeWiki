from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_runner import StubWorker, make_orchestrator  # noqa: E402


def test_executor_completes_and_resumes_after_interruption(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.orchestrator.queue import RunQueue
    from knowledge_compiler.workers.queue_executor import QueueExecutor

    # First execution fails at extraction (simulated interruption/failure).
    failing, queue, _ = make_orchestrator(
        tmp_path, worker=StubWorker(fail_extract=True)
    )
    first = failing.run()
    assert first.status == "failed"

    # A fresh executor over a fresh run resumes the same target cleanly.
    from knowledge_compiler.orchestrator.contracts import TargetState

    resumed_targets = tuple(
        record.model_copy(
            update={
                "state": TargetState.QUEUED,
                "result": None,
                "result_digest": None,
                "published_object_id": None,
                "lease": None,
                "repair_attempts": 0,
                "diagnostics": (),
            }
        )
        for record in queue.record().targets
    )
    from test_runner import FixedClock

    second_queue = RunQueue(
        store_root=tmp_path / ".knowledge/state/runs",
        run=queue.record().model_copy(
            update={"run_id": "orch-run-002", "active": True, "targets": resumed_targets}
        ),
        clock=FixedClock(),
    )
    executor = QueueExecutor.from_queue(
        queue=second_queue,
        snapshot=failing.snapshot,
        evidence_provider=failing.evidence_provider,
        worker=StubWorker(),
        output_root=tmp_path / "out",
        run_id="orch-run-002",
    )
    outcome = executor.execute_all()
    assert outcome.status == "complete"
    assert outcome.published_object_ids == ("module.shop.checkout",)


def test_executor_reentry_on_completed_run_is_idempotent(tmp_path: Path) -> None:
    from knowledge_compiler.workers.queue_executor import QueueExecutor

    orchestrator, queue, _ = make_orchestrator(tmp_path)
    executor = QueueExecutor(
        orchestrator=orchestrator,
        evidence_provider=orchestrator.evidence_provider,
        worker=orchestrator.worker,
    )
    first = executor.execute_all()
    assert first.status == "complete"

    # Re-running over the finalized (inactive, all-done) run does nothing new.
    again = executor.execute_all()
    assert again.status == "complete"
    assert again.published_object_ids == first.published_object_ids
    worker = orchestrator.worker
    assert worker.extract_requests == 1
    assert worker.verify_requests == 1
