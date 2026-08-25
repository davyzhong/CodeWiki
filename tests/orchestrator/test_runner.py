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


class InterruptingVerificationWorker(StubWorker):
    def verify(self, request):
        raise KeyboardInterrupt("simulated process interruption")


class FlexibleFixtureProvider:
    def __init__(self, base) -> None:
        self.base = base

    def build_pack(self, repo, target, budget):
        from knowledge_compiler.contracts.evidence import EvidencePack
        from knowledge_compiler.contracts.repository import PlanTarget

        fixture_target = PlanTarget(
            id="module.shop.checkout",
            type="module",
            topic="CheckoutService",
            evidence_seeds=("CheckoutService", "Inventory.reserve"),
        )
        pack = self.base.build_pack(repo, fixture_target, budget)
        payload = pack.model_dump(mode="json")
        payload["target"] = target.model_dump(mode="json")
        return EvidencePack.model_validate(payload)


class TypedFixtureWorker:
    def __init__(self, knowledge_type: str | None = None) -> None:
        self.knowledge_type = knowledge_type

    def extract(self, request):
        import sys

        sys.path.insert(0, str(ROOT / "tests/contracts"))
        from test_architecture_models import architecture_payload
        from test_flow_models import flow_payload
        from test_rule_models import rule_payload
        from test_tech_stack_models import tech_stack_payload

        from knowledge_compiler.contracts.knowledge import ExtractionResult

        knowledge_type = (
            self.knowledge_type or request.evidence_pack.target.type
        )
        draft = {
            "architecture": architecture_payload,
            "flow": flow_payload,
            "rule": rule_payload,
            "tech-stack": tech_stack_payload,
        }[knowledge_type]()
        draft["scope"] = {
            "repository": request.evidence_pack.repository.repository_id,
            "root": str(request.evidence_pack.repository.root),
            "branch": request.evidence_pack.repository.branch,
            "commit": request.evidence_pack.repository.commit,
            "dirty": request.evidence_pack.repository.dirty,
            "working_tree_hash": (
                request.evidence_pack.repository.working_tree_hash
            ),
        }
        evidence_id = request.evidence_pack.evidence[0].id
        draft["claims"] = [
            {
                **{
                    key: value
                    for key, value in claim.items()
                    if key != "verification"
                },
                "evidence_ids": [evidence_id],
            }
            for claim in draft["claims"]
        ]
        draft["validity"] = None
        return ExtractionResult.model_validate(
            {
                "contract_version": request.contract_version,
                "run_id": request.run_id,
                "target_id": request.target_id,
                "operation": request.operation,
                "attempt": request.attempt,
                "snapshot_id": request.snapshot_id,
                "idempotency_key": request.idempotency_key,
                "draft": draft,
                "provenance": draft["provenance"],
            }
        )

    def verify(self, request):
        from knowledge_compiler.contracts.semantic import VerificationResult

        return VerificationResult.model_validate(
            {
                "contract_version": request.contract_version,
                "run_id": request.run_id,
                "target_id": request.target_id,
                "operation": request.operation,
                "attempt": request.attempt,
                "snapshot_id": request.snapshot_id,
                "idempotency_key": request.idempotency_key,
                "verification_request_digest": (
                    request.verification_request_digest
                ),
                "verifications": [
                    {
                        "claim_id": claim.claim_id,
                        "status": "supported",
                        "verifier": "typed-fixture-verifier",
                        "evidence_ids": [
                            item.evidence_id for item in claim.evidence
                        ],
                        "excerpt_hashes": [
                            item.excerpt_hash for item in claim.evidence
                        ],
                        "excerpts": [item.excerpt for item in claim.evidence],
                        "verification_request_digest": (
                            request.verification_request_digest
                        ),
                    }
                    for claim in request.claims
                ],
            }
        )


class FiveTypeFixtureWorker:
    def __init__(self) -> None:
        self.module = StubWorker()
        self.typed = TypedFixtureWorker()

    def extract(self, request):
        if request.evidence_pack.target.type == "module":
            return self.module.extract(request)
        return self.typed.extract(request)

    def verify(self, request):
        if request.target_id.startswith("module."):
            return self.module.verify(request)
        return self.typed.verify(request)


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
                    "topic": "CheckoutService",
                    "evidence_seeds": (
                        "CheckoutService",
                        "Inventory.reserve",
                    ),
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


def test_runner_uses_the_atomic_generation_publisher(
    tmp_path: Path, monkeypatch
) -> None:
    from knowledge_compiler.storage import GenerationPublisher

    def reject_legacy_publish(*args, **kwargs):
        raise AssertionError("legacy per-object publication was used")

    monkeypatch.setattr(GenerationPublisher, "publish", reject_legacy_publish)
    orchestrator, _, _ = make_orchestrator(tmp_path)

    outcome = orchestrator.run()

    assert outcome.status == "complete"
    assert outcome.published_object_ids == ("module.shop.checkout",)


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


def test_runner_resumes_semantic_verification_after_process_restart(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.orchestrator.runner import RunOrchestrator

    interrupted, queue, tmp = make_orchestrator(
        tmp_path, worker=InterruptingVerificationWorker()
    )
    with pytest.raises(KeyboardInterrupt):
        interrupted.run()

    later = FixedClock()
    later.now = 2_000_000
    resumed_queue = RunQueue(
        store_root=tmp / ".knowledge/state/runs",
        run=queue.record(),
        clock=later,
    )
    resumed_queue.expire_leases()
    resumed = RunOrchestrator(
        queue=resumed_queue,
        snapshot=interrupted.snapshot,
        evidence_provider=interrupted.evidence_provider,
        worker=StubWorker(),
        output_root=interrupted.output_root,
        run_id=interrupted.run_id,
    )

    outcome = resumed.run()

    assert outcome.status == "complete"
    assert outcome.published_object_ids == ("module.shop.checkout",)


def test_runner_resumes_verified_artifact_after_publication_interruption(
    tmp_path: Path, monkeypatch
) -> None:
    from knowledge_compiler.orchestrator.runner import RunOrchestrator
    from knowledge_compiler.storage import GenerationPublisher

    interrupted, queue, tmp = make_orchestrator(tmp_path)
    original = GenerationPublisher.publish_generation
    calls = 0

    def interrupt_once(self, generation, objects):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("publication handoff interrupted")
        return original(self, generation, objects)

    monkeypatch.setattr(
        GenerationPublisher, "publish_generation", interrupt_once
    )
    with pytest.raises(KeyboardInterrupt):
        interrupted.run()
    assert queue.record().targets[0].state is TargetState.VERIFIED

    resumed_queue = RunQueue(
        store_root=tmp / ".knowledge/state/runs",
        run=queue.record(),
        clock=FixedClock(),
    )
    resumed = RunOrchestrator(
        queue=resumed_queue,
        snapshot=interrupted.snapshot,
        evidence_provider=interrupted.evidence_provider,
        worker=StubWorker(fail_extract=True),
        output_root=interrupted.output_root,
        run_id=interrupted.run_id,
    )

    outcome = resumed.run()

    assert outcome.status == "complete", outcome.diagnostics
    assert outcome.published_object_ids == ("module.shop.checkout",)


@pytest.mark.parametrize(
    ("knowledge_type", "target_id", "directory"),
    (
        ("architecture", "architecture.shop.platform", "architecture"),
        ("flow", "flow.shop.checkout", "flows"),
        ("rule", "rule.shop.reservation-first", "rules"),
        ("tech-stack", "tech-stack.shop.platform", "tech-stack"),
    ),
)
def test_runner_drives_typed_targets_through_the_shared_pipeline(
    tmp_path: Path,
    knowledge_type: str,
    target_id: str,
    directory: str,
) -> None:
    from knowledge_compiler.orchestrator.runner import RunOrchestrator

    module_runner, queue, tmp = make_orchestrator(tmp_path)
    typed_target = queue.record().targets[0].model_copy(
        update={
            "target_id": target_id,
            "object_type": knowledge_type,
            "topic": f"{knowledge_type} fixture target",
            "evidence_seeds": ("checkout", "inventory"),
            "request_digest": "sha256:" + "7" * 64,
        }
    )
    typed_run = queue.record().model_copy(
        update={
            "run_id": f"{knowledge_type}-run-001",
            "targets": (typed_target,),
        }
    )
    typed_queue = RunQueue(
        store_root=tmp / f"{knowledge_type}-state",
        run=typed_run,
        clock=FixedClock(),
    )
    runner = RunOrchestrator(
        queue=typed_queue,
        snapshot=module_runner.snapshot,
        evidence_provider=FlexibleFixtureProvider(
            module_runner.evidence_provider
        ),
        worker=TypedFixtureWorker(knowledge_type),
        output_root=tmp / f"{knowledge_type}-out",
        run_id=typed_run.run_id,
    )

    outcome = runner.run()

    assert outcome.status == "complete", outcome.diagnostics
    assert outcome.published_object_ids == (target_id,)
    assert (
        tmp
        / f"{knowledge_type}-out/.knowledge/objects/{directory}/{target_id}.yaml"
    ).is_file()


def test_runner_publishes_all_typed_targets_in_one_generation(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.orchestrator.runner import RunOrchestrator

    module_runner, queue, tmp = make_orchestrator(tmp_path)
    target_specs = (
        ("module", "module.shop.checkout"),
        ("architecture", "architecture.shop.platform"),
        ("flow", "flow.shop.checkout"),
        ("rule", "rule.shop.reservation-first"),
        ("tech-stack", "tech-stack.shop.platform"),
    )
    template = queue.record().targets[0]
    targets = tuple(
        template.model_copy(
            update={
                "target_id": target_id,
                "object_type": knowledge_type,
                "topic": (
                    "CheckoutService"
                    if knowledge_type == "module"
                    else f"{knowledge_type} fixture target"
                ),
                "evidence_seeds": (
                    ("CheckoutService", "Inventory.reserve")
                    if knowledge_type == "module"
                    else ("checkout", "inventory")
                ),
                "request_digest": "sha256:" + str(index + 3) * 64,
            }
        )
        for index, (knowledge_type, target_id) in enumerate(target_specs)
    )
    run = queue.record().model_copy(
        update={"run_id": "typed-batch-run-001", "targets": targets}
    )
    typed_queue = RunQueue(
        store_root=tmp / "typed-batch-state",
        run=run,
        clock=FixedClock(),
    )
    runner = RunOrchestrator(
        queue=typed_queue,
        snapshot=module_runner.snapshot,
        evidence_provider=FlexibleFixtureProvider(
            module_runner.evidence_provider
        ),
        worker=FiveTypeFixtureWorker(),
        output_root=tmp / "typed-batch-out",
        run_id=run.run_id,
    )

    outcome = runner.run()

    assert outcome.status == "complete", outcome.diagnostics
    assert outcome.published_object_ids == tuple(
        sorted(target_id for _, target_id in target_specs)
    )
    import yaml

    manifest = yaml.safe_load(
        (tmp / "typed-batch-out/.knowledge/manifest.yaml").read_bytes()
    )
    assert len(manifest["objects"]) == 5


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
