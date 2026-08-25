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
