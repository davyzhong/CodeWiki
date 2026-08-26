from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_real_provider_slice import make_world


def test_configured_llm_build_requires_user_model_resolution(
    tmp_path: Path, monkeypatch
) -> None:
    from knowledge_compiler.building import BuildConfigurationError, create_llm_worker
    from knowledge_compiler.config import WorkerProfiles

    monkeypatch.delenv("KNOWLEDGE_EXTRACTION_MODEL", raising=False)
    monkeypatch.delenv("KNOWLEDGE_VALIDATION_MODEL", raising=False)

    profiles = WorkerProfiles(
        extraction_profile="extraction-v1", validation_profile=None
    )
    try:
        create_llm_worker(profiles)
    except BuildConfigurationError as error:
        assert "KNOWLEDGE_EXTRACTION_MODEL" in str(error)
    else:
        raise AssertionError("missing user-level model resolution must fail closed")


def test_primary_llm_build_runs_real_provider_contract_through_orchestrator(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.building import run_primary_build

    snapshot, provider, worker, plan = make_world(tmp_path)
    from knowledge_compiler.planning.module import plan_one_module

    outcome = run_primary_build(
        repository_root=snapshot.root,
        executor="llm",
        evidence_provider=provider,
        worker=worker,
        snapshot=snapshot,
        run_id="primary-real-001",
        planner=plan_one_module,
    )

    assert outcome.status == "complete"
    assert outcome.generation is not None
    assert outcome.published_object_ids == (plan.targets[0].target.id,)
    assert (snapshot.root / ".knowledge/manifest.yaml").is_file()


def test_primary_build_records_conflict_when_override_evidence_changes(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.orchestrator.store import RunStore
    from knowledge_compiler.planning.module import plan_one_module

    snapshot, provider, worker, plan = make_world(tmp_path)
    object_id = plan.targets[0].target.id
    first = run_primary_build(
        repository_root=snapshot.root,
        executor="llm",
        evidence_provider=provider,
        worker=worker,
        snapshot=snapshot,
        run_id="overlay-conflict-001",
        planner=plan_one_module,
    )
    assert first.status == "complete"
    canonical_path = (
        snapshot.root / f".knowledge/objects/modules/{object_id}.yaml"
    )
    canonical_before = canonical_path.read_bytes()
    overlay = (
        snapshot.root
        / ".knowledge/human/modules"
        / f"{object_id}.yaml"
    )
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {object_id}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections:\n"
        "  - field: summary\n"
        "    mode: override\n"
        "    text: Human checkout summary.\n"
        "    basis: incident review\n"
        "notes: []\n",
        encoding="utf-8",
    )
    overlay_before = overlay.read_bytes()
    checkout = snapshot.root / "src/shop/checkout.py"
    checkout.write_text(
        checkout.read_text(encoding="utf-8").replace(
            "inventory reservation failed", "stock reservation failed"
        ),
        encoding="utf-8",
    )

    outcome = run_primary_build(
        repository_root=snapshot.root,
        executor="llm",
        evidence_provider=provider,
        worker=worker,
        snapshot=snapshot,
        run_id="overlay-conflict-002",
        planner=plan_one_module,
    )

    assert outcome.status == "partial"
    assert outcome.generation is None
    assert outcome.published_object_ids == ()
    assert "human override conflict" in " ".join(outcome.diagnostics)
    assert canonical_path.read_bytes() == canonical_before
    assert overlay.read_bytes() == overlay_before
    run = RunStore(
        snapshot.root / ".knowledge/state/runs"
    ).load("overlay-conflict-002")
    assert run.targets[0].result.value == "conflicted"


def test_primary_agent_build_prepares_real_queue_without_model_or_publication(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.building import run_primary_build

    snapshot, provider, _, plan = make_world(tmp_path)

    class ForbiddenWorker:
        def extract(self, request):
            raise AssertionError("agent preparation must not call extraction")

        def verify(self, request):
            raise AssertionError("agent preparation must not call verification")

    outcome = run_primary_build(
        repository_root=snapshot.root,
        executor="agent",
        evidence_provider=provider,
        worker=ForbiddenWorker(),
        snapshot=snapshot,
        run_id="primary-agent-001",
    )

    assert outcome.status == "partial"
    assert outcome.generation is None
    assert outcome.published_object_ids == ()
    assert not (snapshot.root / ".knowledge/manifest.yaml").exists()
    run_file = (
        snapshot.root
        / ".knowledge/state/runs/primary-agent-001/run.json"
    )
    payload = json.loads(run_file.read_text(encoding="utf-8"))
    assert payload["executor"] == "agent"
    assert payload["active"] is True
    assert {target["object_type"] for target in payload["targets"]} == {
        "architecture",
        "module",
        "flow",
        "rule",
        "tech-stack",
    }
    assert plan.targets[0].target.id in {
        target["target_id"] for target in payload["targets"]
    }
    assert {target["state"] for target in payload["targets"]} == {
        "evidence_ready"
    }
    evidence_files = list(
        run_file.parent.joinpath("targets").glob("*/evidence.json")
    )
    assert len(evidence_files) == 5
    persisted_plan = json.loads(
        run_file.parent.joinpath("plan.json").read_text(encoding="utf-8")
    )
    assert len(persisted_plan["targets"]) == 5
    assert persisted_plan["run_id"] == "primary-agent-001"


def test_primary_agent_build_resumes_the_active_run_instead_of_forking(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.building import run_primary_build

    snapshot, provider, _, _ = make_world(tmp_path)
    first = run_primary_build(
        repository_root=snapshot.root,
        executor="agent",
        evidence_provider=provider,
        snapshot=snapshot,
    )
    second = run_primary_build(
        repository_root=snapshot.root,
        executor="agent",
        evidence_provider=provider,
        snapshot=snapshot,
    )

    assert second.status == "partial"
    assert second.run_id == first.run_id
    runs = list((snapshot.root / ".knowledge/state/runs").glob("*/run.json"))
    assert len(runs) == 1


def test_agent_queue_schedules_more_than_the_first_planned_target(
    tmp_path: Path, monkeypatch
) -> None:
    from typer.testing import CliRunner

    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.cli import app

    snapshot, provider, _, _ = make_world(tmp_path)
    run_primary_build(
        repository_root=snapshot.root,
        executor="agent",
        evidence_provider=provider,
        snapshot=snapshot,
    )
    monkeypatch.chdir(snapshot.root)
    runner = CliRunner()

    first = runner.invoke(app, ["next", "--operation", "extraction"])
    second = runner.invoke(app, ["next", "--operation", "extraction"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert json.loads(first.output)["target_id"] != json.loads(second.output)[
        "target_id"
    ]


def test_agent_protocol_validates_contracts_and_publishes_generation(
    tmp_path: Path, monkeypatch
) -> None:
    from typer.testing import CliRunner

    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.cli import app
    from knowledge_compiler.contracts.semantic import (
        ExtractionRequest,
        VerificationRequest,
    )
    from knowledge_compiler.planning.module import plan_one_module
    from test_typed_publication import canonicalize

    snapshot, provider, worker, plan = make_world(tmp_path)
    preserved_flow = canonicalize("flow").canonical
    assert preserved_flow is not None
    outcome = run_primary_build(
        repository_root=snapshot.root,
        executor="agent",
        evidence_provider=provider,
        snapshot=snapshot,
        run_id="agent-contract-001",
        planner=plan_one_module,
        preserved_items=((preserved_flow, None),),
    )
    monkeypatch.chdir(snapshot.root)
    runner = CliRunner()

    next_extraction = runner.invoke(
        app, ["next", "--operation", "extraction"]
    )
    assert next_extraction.exit_code == 0, next_extraction.output
    extraction_work = json.loads(next_extraction.output)
    extraction_request = ExtractionRequest.model_validate(
        extraction_work["request"]
    )
    extraction = worker.extract(extraction_request)
    extraction_file = tmp_path / "extraction.json"
    extraction_file.write_text(
        extraction.model_dump_json(), encoding="utf-8"
    )
    tampered_file = tmp_path / "tampered-extraction.json"
    tampered_file.write_text(
        extraction.model_copy(update={"run_id": "foreign-run"}).model_dump_json(),
        encoding="utf-8",
    )
    rejected = runner.invoke(
        app,
        [
            "submit-extraction",
            str(tampered_file),
            "--lease",
            extraction_work["lease"]["token"],
        ],
    )
    assert rejected.exit_code == 1
    assert "envelope" in rejected.output.lower()
    submitted = runner.invoke(
        app,
        [
            "submit-extraction",
            str(extraction_file),
            "--lease",
            extraction_work["lease"]["token"],
        ],
    )
    assert submitted.exit_code == 0, submitted.output

    verification_work = runner.invoke(app, ["verify-next"])
    assert verification_work.exit_code == 0, verification_work.output
    verification_request = VerificationRequest.model_validate(
        json.loads(verification_work.output)["request"]
    )
    verification = worker.verify(verification_request)
    verification_file = tmp_path / "verification.json"
    verification_file.write_text(
        verification.model_dump_json(), encoding="utf-8"
    )
    verification_lease = runner.invoke(
        app, ["next", "--operation", "verification"]
    )
    assert verification_lease.exit_code == 0, verification_lease.output
    lease = json.loads(verification_lease.output)["lease"]["token"]
    wrong_lease = runner.invoke(
        app,
        [
            "submit-verification",
            str(verification_file),
            "--lease",
            "wrong-token",
        ],
    )
    assert wrong_lease.exit_code == 1
    accepted = runner.invoke(
        app,
        [
            "submit-verification",
            str(verification_file),
            "--lease",
            lease,
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget

    pending_path = snapshot.root / ".knowledge/state/pending-targets.json"
    PendingStore(pending_path).add(
        PersistedTarget(
            target_id=plan.targets[0].target.id,
            reason="evidence-changed",
        )
    )

    finalized = runner.invoke(app, ["finalize"])

    assert finalized.exit_code == 0, finalized.output
    payload = json.loads(finalized.output)
    assert payload["status"] == "complete"
    assert payload["published_object_ids"] == [plan.targets[0].target.id]
    assert (snapshot.root / ".knowledge/manifest.yaml").is_file()
    import yaml

    manifest = yaml.safe_load(
        (snapshot.root / ".knowledge/manifest.yaml").read_bytes()
    )
    assert {item["id"] for item in manifest["objects"]} == {
        plan.targets[0].target.id,
        preserved_flow.id,
    }
    assert PendingStore(pending_path).target_ids() == set()
    report = json.loads(
        (snapshot.root / ".knowledge/state/runs/last-build.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["status"] == "complete"
    assert report["executor"] == "agent"


def test_changed_evidence_atomically_marks_canonical_stale_and_removes_card(
    tmp_path: Path,
) -> None:
    import yaml

    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.incremental.invalidation import (
        invalidate_changed_knowledge,
    )
    from knowledge_compiler.incremental.pending import PendingStore
    from knowledge_compiler.planning.module import plan_one_module
    from knowledge_compiler.repository.changes import ChangeSet

    snapshot, provider, worker, plan = make_world(tmp_path)
    built = run_primary_build(
        repository_root=snapshot.root,
        executor="llm",
        evidence_provider=provider,
        worker=worker,
        snapshot=snapshot,
        run_id="invalidation-source-001",
        planner=plan_one_module,
    )
    object_id = plan.targets[0].target.id
    card = snapshot.root / f".knowledge/views/cards/{object_id}.md"
    assert card.is_file()

    invalidated = invalidate_changed_knowledge(
        repository_root=snapshot.root,
        change_set=ChangeSet(modified=("src/shop/checkout.py",)),
    )

    assert invalidated.stale == (object_id,)
    assert invalidated.generation != built.generation
    canonical = yaml.safe_load(
        (snapshot.root / f".knowledge/objects/modules/{object_id}.yaml").read_bytes()
    )
    assert canonical["validity"]["status"] == "stale"
    assert not card.exists()
    pending = PendingStore(
        snapshot.root / ".knowledge/state/pending-targets.json"
    )
    assert pending.target_ids() == {object_id}


def test_failed_regeneration_after_safe_invalidation_is_partial_and_retryable(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.cli import _default_config
    from knowledge_compiler.incremental.updating import run_incremental_update
    from knowledge_compiler.planning.module import plan_one_module
    from knowledge_compiler.repository.inventory import FileRecord, load_baseline, save_baseline
    from knowledge_compiler.repository.local_git import LocalGitRepositoryProvider

    snapshot, provider, worker, plan = make_world(tmp_path)
    run_primary_build(
        repository_root=snapshot.root,
        executor="llm",
        evidence_provider=provider,
        worker=worker,
        snapshot=snapshot,
        run_id="update-source-001",
        planner=plan_one_module,
    )
    git_provider = LocalGitRepositoryProvider()
    before = tuple(
        FileRecord(
            path=item.path,
            blob_id=item.blob_id,
            content_hash=item.content_hash,
            size=item.size,
            language=item.language,
        )
        for item in git_provider.inventory(snapshot.root)
        if item.supported
    )
    baseline_path = snapshot.root / ".knowledge/baseline/eligible-files.json"
    save_baseline(baseline_path, before)
    checkout = snapshot.root / "src/shop/checkout.py"
    checkout.write_text(
        checkout.read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )

    def failing_build(**kwargs):
        raise RuntimeError("provider unavailable")

    outcome = run_incremental_update(
        repository_root=snapshot.root,
        executor="llm",
        config=_default_config("zh"),
        build_runner=failing_build,
    )

    assert outcome.status == "partial"
    assert outcome.stale_object_ids == (plan.targets[0].target.id,)
    assert outcome.pending_target_ids == (plan.targets[0].target.id,)
    assert "regeneration failed" in outcome.diagnostics[0]
    advanced = load_baseline(baseline_path)
    checkout_record = next(
        item for item in advanced if item.path == "src/shop/checkout.py"
    )
    assert checkout_record.content_hash != next(
        item for item in before if item.path == "src/shop/checkout.py"
    ).content_hash


def test_no_diff_pending_retry_selects_target_and_preserves_healthy_generation(
    tmp_path: Path,
) -> None:
    from test_typed_publication import canonicalize

    from knowledge_compiler.building import PrimaryBuildOutcome
    from knowledge_compiler.cli import _default_config
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget
    from knowledge_compiler.incremental.updating import run_incremental_update
    from knowledge_compiler.repository.inventory import FileRecord, save_baseline
    from knowledge_compiler.repository.local_git import LocalGitRepositoryProvider
    from knowledge_compiler.storage import GenerationPublisher

    snapshot, _, _, _ = make_world(tmp_path)
    architecture = canonicalize("architecture").canonical
    flow = canonicalize("flow").canonical
    assert architecture is not None
    assert flow is not None
    GenerationPublisher(snapshot.root).publish_generation(
        "gen-selective-base", ((architecture, None), (flow, None))
    )
    inventory = tuple(
        FileRecord(
            path=item.path,
            blob_id=item.blob_id,
            content_hash=item.content_hash,
            size=item.size,
            language=item.language,
        )
        for item in LocalGitRepositoryProvider().inventory(snapshot.root)
        if item.supported
    )
    save_baseline(
        snapshot.root / ".knowledge/baseline/eligible-files.json",
        inventory,
    )
    PendingStore(
        snapshot.root / ".knowledge/state/pending-targets.json"
    ).add(PersistedTarget(target_id=architecture.id, reason="retry"))
    captured = {}

    def selective_build(**kwargs):
        captured.update(kwargs)
        return PrimaryBuildOutcome(
            status="partial",
            generation=None,
            published_object_ids=(),
            diagnostics=("semantic work pending",),
            run_id="selective-001",
        )

    outcome = run_incremental_update(
        repository_root=snapshot.root,
        executor="agent",
        config=_default_config("zh"),
        build_runner=selective_build,
    )

    assert outcome.status == "partial"
    assert captured["target_ids"] == frozenset({architecture.id})
    assert tuple(item[0].id for item in captured["preserved_items"]) == (
        flow.id,
    )


@pytest.mark.parametrize(
    ("search_complete", "expected_status"),
    ((True, "complete"), (False, "partial")),
)
def test_deleted_target_retirement_obeys_deterministic_proof_boundary(
    tmp_path: Path,
    search_complete: bool,
    expected_status: str,
) -> None:
    import yaml

    from test_typed_publication import canonicalize

    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.cli import _default_config
    from knowledge_compiler.incremental.retirement import RetirementCheck
    from knowledge_compiler.incremental.updating import run_incremental_update
    from knowledge_compiler.planning.module import plan_one_module
    from knowledge_compiler.repository.inventory import FileRecord, save_baseline
    from knowledge_compiler.repository.local_git import LocalGitRepositoryProvider

    snapshot, provider, worker, plan = make_world(tmp_path)
    flow = canonicalize("flow").canonical
    assert flow is not None
    run_primary_build(
        repository_root=snapshot.root,
        executor="llm",
        evidence_provider=provider,
        worker=worker,
        snapshot=snapshot,
        run_id="retirement-source-001",
        planner=plan_one_module,
        preserved_items=((flow, None),),
    )
    inventory = tuple(
        FileRecord(
            path=item.path,
            blob_id=item.blob_id,
            content_hash=item.content_hash,
            size=item.size,
            language=item.language,
        )
        for item in LocalGitRepositoryProvider().inventory(snapshot.root)
        if item.supported
    )
    save_baseline(
        snapshot.root / ".knowledge/baseline/eligible-files.json",
        inventory,
    )
    (snapshot.root / "src/shop/checkout.py").unlink()
    (snapshot.root / "src/shop/inventory.py").unlink()
    object_id = plan.targets[0].target.id
    overlay_path = (
        snapshot.root / ".knowledge/human/modules" / f"{object_id}.yaml"
    )
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {object_id}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections:\n"
        "  - field: summary\n"
        "    mode: supplement\n"
        "    text: Human checkout summary.\n"
        "    basis: incident review\n"
        "notes: []\n",
        encoding="utf-8",
    )
    overlay_bytes = overlay_path.read_bytes()

    def planner_omitted(**kwargs):
        raise ValueError("pending target is absent from refreshed plan")

    def prove(candidate):
        return RetirementCheck(
            candidate=candidate,
            source_absent=True,
            search_complete=search_complete,
            search_found_current=False,
            inbound_relations_verified=True,
        )

    outcome = run_incremental_update(
        repository_root=snapshot.root,
        executor="llm",
        config=_default_config("zh"),
        build_runner=planner_omitted,
        retirement_prover=prove,
    )

    assert outcome.status == expected_status
    object_path = (
        snapshot.root / f".knowledge/objects/modules/{object_id}.yaml"
    )
    manifest = yaml.safe_load(
        (snapshot.root / ".knowledge/manifest.yaml").read_bytes()
    )
    archive_path = (
        snapshot.root
        / ".knowledge/human/archive/modules"
        / f"{object_id}.yaml"
    )
    if search_complete:
        assert outcome.retired_object_ids == (object_id,)
        assert outcome.pending_target_ids == ()
        assert not object_path.exists()
        assert manifest["objects"] == [{"id": flow.id, "type": "flow"}]
        assert not overlay_path.exists()
        assert archive_path.read_bytes() == overlay_bytes
    else:
        assert outcome.retired_object_ids == ()
        assert outcome.pending_target_ids == (object_id,)
        assert yaml.safe_load(object_path.read_bytes())["validity"]["status"] == "stale"
        assert {item["id"] for item in manifest["objects"]} == {
            flow.id,
            object_id,
        }
        assert overlay_path.read_bytes() == overlay_bytes
        assert not archive_path.exists()
