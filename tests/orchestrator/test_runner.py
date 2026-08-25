from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from knowledge_compiler.orchestrator.contracts import (
    RunRecord,
    TargetState,
    TerminalResult,
)
from knowledge_compiler.orchestrator.queue import RunQueue


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fake_provider"
REPOSITORY_ROOT = (ROOT / "tests/fixtures/probe_repo").resolve()


class FixedClock:
    def __init__(self) -> None:
        self.now = 1_000_000

    def __call__(self) -> int:
        return self.now


class StubWorker:
    """Deterministic worker returning fixture drafts/verifications."""

    def __init__(self, fail_extract: bool = False, fail_verify: bool = False):
        self.fail_extract = fail_extract
        self.fail_verify = fail_verify
        self.extract_requests = 0
        self.verify_requests = 0

    def extract(self, request):
        from knowledge_compiler.workers.litellm_worker import WorkerTransportError

        self.extract_requests += 1
        if self.fail_extract:
            raise WorkerTransportError("model transport failed: down")
        from knowledge_compiler.contracts.knowledge import ExtractionResult

        payload = json.loads(
            (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
        )
        payload["draft"]["scope"] = {
            "repository": request.evidence_pack.repository.repository_id,
            "root": str(request.evidence_pack.repository.root),
            "branch": request.evidence_pack.repository.branch,
            "commit": request.evidence_pack.repository.commit,
            "dirty": request.evidence_pack.repository.dirty,
            "working_tree_hash": request.evidence_pack.repository.working_tree_hash,
        }
        for field in (
            "contract_version", "run_id", "target_id", "operation",
            "attempt", "snapshot_id", "idempotency_key",
        ):
            payload[field] = getattr(request, field)
        return ExtractionResult.model_validate(payload)

    def verify(self, request):
        from knowledge_compiler.workers.litellm_worker import WorkerTransportError

        self.verify_requests += 1
        if self.fail_verify:
            raise WorkerTransportError("model transport failed: down")
        from knowledge_compiler.contracts.semantic import VerificationResult

        payload = json.loads(
            (FIXTURES / "module-verification.json").read_text(encoding="utf-8")
        )
        for field in (
            "contract_version", "run_id", "target_id", "operation",
            "attempt", "snapshot_id", "idempotency_key",
        ):
            payload[field] = getattr(request, field)
        return VerificationResult.model_validate(payload)


def make_orchestrator(
    tmp_path: Path,
    worker: StubWorker | None = None,
):
    from knowledge_compiler.contracts.repository import (
        RepositorySnapshot,
        build_snapshot_id,
    )
    from knowledge_compiler.orchestrator.runner import RunOrchestrator
    from knowledge_compiler.providers.fake import FakeEvidenceProvider

    repository_id = "fixture/probe-shop"
    commit = "probe-fixture-v1"
    snapshot = RepositorySnapshot.model_validate(
        {
            "repository_id": repository_id,
            "snapshot_id": build_snapshot_id(repository_id, commit, False, None),
            "root": REPOSITORY_ROOT,
            "branch": "main",
            "commit": commit,
            "dirty": False,
            "working_tree_hash": None,
            "eligible_files": (
                "pyproject.toml",
                "src/shop/__init__.py",
                "src/shop/api.py",
                "src/shop/checkout.py",
                "src/shop/inventory.py",
            ),
        }
    )
    provider = FakeEvidenceProvider(
        fixture_dir=FIXTURES, repository_root=REPOSITORY_ROOT
    )
    run_record = RunRecord.model_validate(
        {
            "run_id": "orch-run-001",
            "repository_id": repository_id,
            "snapshot_id": snapshot.snapshot_id,
            "executor": "llm",
            "active": True,
            "targets": (
                {
                    "target_id": "module.shop.checkout",
                    "object_type": "module",
                    "state": "queued",
                    "attempt": 1,
                    "repair_attempts": 0,
                    "required": True,
                    "priority": 1,
                    "result": None,
                    "published_object_id": None,
                    "request_digest": "sha256:" + "1" * 64,
                    "result_digest": None,
                    "diagnostics": (),
                    "lease": None,
                },
            ),
        }
    )
    queue = RunQueue(
        store_root=tmp_path / ".knowledge/state/runs",
        run=run_record,
        clock=FixedClock(),
    )
    orchestrator = RunOrchestrator(
        queue=queue,
        snapshot=snapshot,
        evidence_provider=provider,
        worker=worker or StubWorker(),
        output_root=tmp_path / "out",
        run_id="orch-run-001",
    )
    return orchestrator, queue, tmp_path


def test_runner_publishes_one_generation_and_completes(tmp_path: Path) -> None:
    orchestrator, queue, tmp = make_orchestrator(tmp_path)
    outcome = orchestrator.run()

    assert outcome.status == "complete"
    assert outcome.published_object_ids == ("module.shop.checkout",)
    record = queue.record()
    assert record.active is False
    target = record.targets[0]
    assert target.state is TargetState.VERIFIED
    manifest = json.loads(
        (tmp / "out/.knowledge/manifest.yaml").read_text(encoding="utf-8").replace(
            "active_generation:", '"active_generation":'
        ).replace("agent_views_generation:", '"agent_views_generation":').replace(
            "wiki_generation:", '"wiki_generation":'
        )
    ) if False else None
    import yaml

    manifest = yaml.safe_load((tmp / "out/.knowledge/manifest.yaml").read_bytes())
    assert manifest["active_generation"] == outcome.generation


def test_runner_model_failure_fails_without_publication(tmp_path: Path) -> None:
    orchestrator, queue, tmp = make_orchestrator(tmp_path, worker=StubWorker(fail_extract=True))
    outcome = orchestrator.run()
    assert outcome.status == "failed"
    assert outcome.published_object_ids == ()
    assert not (tmp / "out/.knowledge/manifest.yaml").exists()
    target = queue.record().targets[0]
    assert target.state is TargetState.DONE
    assert target.result is TerminalResult.INVALID


def test_runner_verify_failure_is_partial_not_published(tmp_path: Path) -> None:
    orchestrator, queue, tmp = make_orchestrator(tmp_path, worker=StubWorker(fail_verify=True))
    outcome = orchestrator.run()
    assert outcome.status == "failed"
    assert not (tmp / "out/.knowledge/manifest.yaml").exists()


def test_runner_preserves_previous_generation_on_failure(tmp_path: Path) -> None:
    first_orchestrator, _, tmp = make_orchestrator(tmp_path)
    first = first_orchestrator.run()
    assert first.status == "complete"
    manifest_before = (tmp / "out/.knowledge/manifest.yaml").read_bytes()

    # A second run over the same output root with a failing worker must
    # leave the committed generation byte-identical.
    from knowledge_compiler.contracts.repository import (
        RepositorySnapshot,
        build_snapshot_id,
    )
    from knowledge_compiler.orchestrator.queue import RunQueue
    from knowledge_compiler.orchestrator.runner import RunOrchestrator
    from knowledge_compiler.providers.fake import FakeEvidenceProvider

    repository_id = "fixture/probe-shop"
    commit = "probe-fixture-v1"
    snapshot = RepositorySnapshot.model_validate(
        {
            "repository_id": repository_id,
            "snapshot_id": build_snapshot_id(repository_id, commit, False, None),
            "root": REPOSITORY_ROOT,
            "branch": "main",
            "commit": commit,
            "dirty": False,
            "working_tree_hash": None,
            "eligible_files": (
                "pyproject.toml",
                "src/shop/__init__.py",
                "src/shop/api.py",
                "src/shop/checkout.py",
                "src/shop/inventory.py",
            ),
        }
    )
    from knowledge_compiler.orchestrator.contracts import TargetState as _TS

    fresh_targets = tuple(
        record.model_copy(
            update={
                "state": _TS.QUEUED,
                "result": None,
                "result_digest": None,
                "published_object_id": None,
                "lease": None,
                "repair_attempts": 0,
            }
        )
        for record in first_orchestrator.queue.record().targets
    )
    second_queue = RunQueue(
        store_root=tmp / ".knowledge/state/runs",
        run=first_orchestrator.queue.record().model_copy(
            update={
                "run_id": "orch-run-002",
                "active": True,
                "targets": fresh_targets,
            }
        ),
        clock=FixedClock(),
    )
    second = RunOrchestrator(
        queue=second_queue,
        snapshot=snapshot,
        evidence_provider=FakeEvidenceProvider(
            fixture_dir=FIXTURES, repository_root=REPOSITORY_ROOT
        ),
        worker=StubWorker(fail_extract=True),
        output_root=tmp_path / "out",
        run_id="orch-run-002",
    )
    outcome = second.run()
    assert outcome.status == "failed"
    assert (tmp / "out/.knowledge/manifest.yaml").read_bytes() == manifest_before
