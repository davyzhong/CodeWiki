from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts.planning import KnowledgePlan, PlanTargetSpec
from knowledge_compiler.contracts.repository import (
    PlanTarget,
    RepositorySnapshot,
    build_snapshot_id,
)
from knowledge_compiler.orchestrator.contracts import (
    RunRecord,
    TargetRecord,
    TargetState,
    TerminalResult,
)


def _snapshot(root: Path, *, commit: str = "commit-one") -> RepositorySnapshot:
    repository_id = "example/lifecycle-repo"
    return RepositorySnapshot(
        repository_id=repository_id,
        snapshot_id=build_snapshot_id(repository_id, commit, False, None),
        root=root.resolve(),
        branch="main",
        commit=commit,
        dirty=False,
        working_tree_hash=None,
        eligible_files=("src/app.py",),
    )


def _plan() -> KnowledgePlan:
    return KnowledgePlan(
        run_id="lifecycle-run-001",
        repository_id="example/lifecycle-repo",
        snapshot_id="snapshot-lifecycle-001",
        attempt=1,
        idempotency_key="lifecycle-run-001:plan:1:snapshot-lifecycle-001",
        targets=(
            PlanTargetSpec(
                target=PlanTarget(
                    id="module.lifecycle.alpha",
                    type="module",
                    topic="SOURCE_BODY_MUST_NOT_BE_TRACKED",
                    evidence_seeds=("PROVIDER_SECRET_MUST_NOT_BE_TRACKED",),
                ),
                priority=2,
                required=True,
            ),
            PlanTargetSpec(
                target=PlanTarget(
                    id="rule.lifecycle.beta",
                    type="rule",
                    topic="Lifecycle beta",
                    evidence_seeds=("Beta",),
                ),
                priority=4,
                required=False,
            ),
        ),
    )


def _target(
    target_id: str,
    object_type: str,
    priority: int,
    *,
    state: TargetState = TargetState.QUEUED,
    required: bool = True,
) -> TargetRecord:
    return TargetRecord.model_validate(
        {
            "target_id": target_id,
            "object_type": object_type,
            "state": state,
            "attempt": 1,
            "repair_attempts": 0,
            "required": required,
            "priority": priority,
            "result": None,
            "published_object_id": None,
            "request_digest": "sha256:" + "1" * 64,
            "result_digest": None,
            "diagnostics": (),
            "lease": None,
        }
    )


def _run() -> RunRecord:
    return RunRecord(
        run_id="lifecycle-run-001",
        repository_id="example/lifecycle-repo",
        snapshot_id="snapshot-lifecycle-001",
        executor="agent",
        active=True,
        targets=(
            _target("module.lifecycle.alpha", "module", 2),
            _target(
                "rule.lifecycle.beta",
                "rule",
                4,
                required=False,
            ),
        ),
    )


def _terminal_run() -> RunRecord:
    run = _run()
    alpha = run.targets[0].model_copy(
        update={
            "state": TargetState.VERIFIED,
            "published_object_id": "module.lifecycle.alpha",
        }
    )
    beta = run.targets[1].finish(
        TerminalResult.SKIPPED,
        diagnostics=("API_KEY=must-not-be-tracked",),
    )
    return run.model_copy(update={"active": False, "targets": (alpha, beta)})


def test_run_store_projects_strict_secret_free_latest_plan(tmp_path: Path) -> None:
    from knowledge_compiler.orchestrator.store import RunStore

    store = RunStore(tmp_path / ".knowledge/state/runs")
    store.save(_run())
    store.save_plan("lifecycle-run-001", _plan())
    store.save(_terminal_run())

    tracked = tmp_path / ".knowledge/plan.yaml"
    payload = yaml.safe_load(tracked.read_bytes())
    assert payload["schema_version"] == "0.1"
    assert payload["run_id"] == "lifecycle-run-001"
    assert payload["active"] is False
    assert payload["targets"] == [
        {
            "target_id": "module.lifecycle.alpha",
            "object_type": "module",
            "required": True,
            "priority": 2,
            "state": "verified",
            "result": None,
            "published_object_id": "module.lifecycle.alpha",
            "attempt": 1,
            "repair_attempts": 0,
            "pending": False,
        },
        {
            "target_id": "rule.lifecycle.beta",
            "object_type": "rule",
            "required": False,
            "priority": 4,
            "state": "done",
            "result": "skipped",
            "published_object_id": None,
            "attempt": 1,
            "repair_attempts": 0,
            "pending": False,
        },
    ]
    rendered = tracked.read_text(encoding="utf-8")
    assert "SOURCE_BODY_MUST_NOT_BE_TRACKED" not in rendered
    assert "PROVIDER_SECRET_MUST_NOT_BE_TRACKED" not in rendered
    assert "API_KEY=must-not-be-tracked" not in rendered
    assert (tmp_path / ".knowledge/state/runs/lifecycle-run-001/plan.json").is_file()


@pytest.mark.parametrize(
    "failure_point",
    (
        "plan.stage.write",
        "plan.stage.flush",
        "plan.stage.fsync",
        "plan.replace",
        "plan.directory.fsync",
    ),
)
def test_latest_plan_crash_leaves_exact_old_or_new_bytes(
    tmp_path: Path, failure_point: str
) -> None:
    from knowledge_compiler.storage.lifecycle import (
        LifecycleWriteError,
        save_latest_plan,
    )

    save_latest_plan(tmp_path, _plan(), _run())
    path = tmp_path / ".knowledge/plan.yaml"
    old_bytes = path.read_bytes()

    def fail(point: str) -> None:
        if point == failure_point:
            raise OSError(f"injected at {point}")

    with pytest.raises(LifecycleWriteError, match=failure_point):
        save_latest_plan(
            tmp_path,
            _plan(),
            _terminal_run(),
            fault_injector=fail,
        )
    crashed_bytes = path.read_bytes()

    save_latest_plan(tmp_path, _plan(), _terminal_run())
    new_bytes = path.read_bytes()
    assert crashed_bytes in {old_bytes, new_bytes}
    assert not path.with_name("plan.yaml.tmp").exists()


def test_latest_plan_rejects_a_symlink_destination(tmp_path: Path) -> None:
    from knowledge_compiler.storage.lifecycle import (
        LifecycleWriteError,
        save_latest_plan,
    )

    knowledge = tmp_path / ".knowledge"
    knowledge.mkdir()
    decoy = tmp_path / "decoy.yaml"
    decoy.write_text("keep: exact\n", encoding="utf-8")
    (knowledge / "plan.yaml").symlink_to(decoy)

    with pytest.raises(LifecycleWriteError, match="symlink"):
        save_latest_plan(tmp_path, _plan(), _run())
    assert decoy.read_bytes() == b"keep: exact\n"


@pytest.mark.parametrize(
    "failure_point",
    (
        "stage.manifest.write",
        "backup.manifest.write",
        "journal.replace",
        "publish.manifest.replace",
        "publish.manifest.directory.fsync",
    ),
)
def test_manifest_lifecycle_crash_recovers_exact_old_or_new_bytes(
    tmp_path: Path, failure_point: str
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher, PublicationError

    module, pack = _verified_inputs()
    old_snapshot = _snapshot(tmp_path, commit="commit-one")
    new_snapshot = _snapshot(tmp_path, commit="commit-two")
    publisher = GenerationPublisher(tmp_path)
    publisher.publish_generation(
        "gen-lifecycle-old",
        ((module, pack),),
        observed_snapshot=old_snapshot,
        pending_targets=("rule.z", "module.a"),
    )
    manifest_path = tmp_path / ".knowledge/manifest.yaml"
    old_bytes = manifest_path.read_bytes()
    assert yaml.safe_load(old_bytes)["pending_targets"] == [
        "module.a",
        "rule.z",
    ]

    expected_root = tmp_path / "expected"
    GenerationPublisher(expected_root).publish_generation(
        "gen-lifecycle-old",
        ((module, pack),),
        observed_snapshot=old_snapshot.model_copy(update={"root": expected_root}),
        pending_targets=("rule.z", "module.a"),
    )
    GenerationPublisher(expected_root).publish_generation(
        "gen-lifecycle-new",
        ((module, pack),),
        observed_snapshot=new_snapshot.model_copy(update={"root": expected_root}),
        pending_targets=("module.b",),
    )
    new_bytes = (expected_root / ".knowledge/manifest.yaml").read_bytes()

    def fail(point: str) -> None:
        if point == failure_point:
            raise OSError(f"injected at {point}")

    with pytest.raises(PublicationError, match=failure_point):
        GenerationPublisher(tmp_path, fault_injector=fail).publish_generation(
            "gen-lifecycle-new",
            ((module, pack),),
            observed_snapshot=new_snapshot,
            pending_targets=("module.b",),
        )

    GenerationPublisher(tmp_path).recover()
    assert manifest_path.read_bytes() in {old_bytes, new_bytes}


def test_interrupted_manifest_lifecycle_recovery_is_idempotent(tmp_path: Path) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher, PublicationError

    module, pack = _verified_inputs()
    old_snapshot = _snapshot(tmp_path, commit="commit-one")
    old = GenerationPublisher(tmp_path).publish_generation(
        "gen-lifecycle-old",
        ((module, pack),),
        observed_snapshot=old_snapshot,
        pending_targets=("module.old",),
    ).manifest_path.read_bytes()

    def fail_publish(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError(point)

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=fail_publish).publish_generation(
            "gen-lifecycle-new",
            ((module, pack),),
            observed_snapshot=_snapshot(tmp_path, commit="commit-two"),
            pending_targets=("module.new",),
        )

    def fail_recovery(point: str) -> None:
        if point == "recovery.manifest.replace":
            raise OSError(point)

    with pytest.raises(PublicationError, match="recovery.manifest.replace"):
        GenerationPublisher(tmp_path, fault_injector=fail_recovery).recover()
    GenerationPublisher(tmp_path).recover()
    GenerationPublisher(tmp_path).recover()
    assert (tmp_path / ".knowledge/manifest.yaml").read_bytes() == old


def test_pending_only_projection_preserves_committed_observed_snapshot(
    tmp_path: Path,
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget
    from knowledge_compiler.storage import GenerationPublisher
    from knowledge_compiler.storage.lifecycle import save_observed_snapshot_state

    module, pack = _verified_inputs()
    committed = _snapshot(tmp_path, commit="commit-one")
    GenerationPublisher(tmp_path).publish_generation(
        "gen-lifecycle-committed",
        ((module, pack),),
        observed_snapshot=committed,
        pending_targets=(),
    )
    save_observed_snapshot_state(
        tmp_path,
        _snapshot(tmp_path, commit="commit-staged-but-unpublished"),
    )

    PendingStore(
        tmp_path / ".knowledge/state/pending-targets.json"
    ).add(PersistedTarget(target_id="module.retry", reason="retry"))

    manifest = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["observed_snapshot"]["commit"] == committed.commit
    assert manifest["observed_snapshot"]["snapshot_id"] == committed.snapshot_id
    assert manifest["pending_targets"] == ["module.retry"]


def test_publication_without_lifecycle_arguments_retains_known_manifest_state(
    tmp_path: Path,
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher

    module, pack = _verified_inputs()
    observed = _snapshot(tmp_path)
    publisher = GenerationPublisher(tmp_path)
    publisher.publish_generation(
        "gen-lifecycle-known",
        ((module, pack),),
        observed_snapshot=observed,
        pending_targets=("rule.z", "module.a"),
    )

    publisher.publish_generation(
        "gen-lifecycle-compatible",
        ((module, pack),),
    )

    manifest = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["observed_snapshot"]["snapshot_id"] == observed.snapshot_id
    assert manifest["pending_targets"] == ["module.a", "rule.z"]
