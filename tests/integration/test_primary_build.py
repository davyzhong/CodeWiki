from __future__ import annotations

import json
from pathlib import Path

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

    snapshot, provider, worker, plan = make_world(tmp_path)
    outcome = run_primary_build(
        repository_root=snapshot.root,
        executor="agent",
        evidence_provider=provider,
        snapshot=snapshot,
        run_id="agent-contract-001",
        planner=plan_one_module,
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

    finalized = runner.invoke(app, ["finalize"])

    assert finalized.exit_code == 0, finalized.output
    payload = json.loads(finalized.output)
    assert payload["status"] == "complete"
    assert payload["published_object_ids"] == [plan.targets[0].target.id]
    assert (snapshot.root / ".knowledge/manifest.yaml").is_file()
    report = json.loads(
        (snapshot.root / ".knowledge/state/runs/last-build.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["status"] == "complete"
    assert report["executor"] == "agent"
