from __future__ import annotations

import multiprocessing
import os
import threading
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


_PENDING_TRANSACTION_FAILURE_POINTS = (
    "pending-lifecycle.journal.replace",
    "pending-lifecycle.journal.directory.fsync",
    "pending-lifecycle.pending.replace",
    "pending-lifecycle.pending.directory.fsync",
    "pending-lifecycle.plan.replace",
    "pending-lifecycle.plan.directory.fsync",
    "pending-lifecycle.manifest.replace",
    "pending-lifecycle.manifest.directory.fsync",
    "pending-lifecycle.cleanup.directory.fsync",
)


class _SimulatedProcessDeath(BaseException):
    pass


def _crash_pending_in_child(
    root: str,
    start_pending,
    lock_contended,
    pending_finished,
) -> None:
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget
    from knowledge_compiler.storage import lifecycle

    start_pending.wait()
    lifecycle._LOCK_CONTENTION_HOOK = lock_contended.set

    def crash(point: str) -> None:
        if point == "pending-lifecycle.plan.replace":
            raise _SimulatedProcessDeath(point)

    try:
        PendingStore(
            Path(root) / ".knowledge/state/pending-targets.json",
            fault_injector=crash,
        ).add(PersistedTarget(target_id="module.lifecycle.alpha", reason="retry"))
    except _SimulatedProcessDeath:
        pass
    finally:
        pending_finished.set()


def _crash_generation_in_child(root: str, operation: str) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher

    module, pack = _verified_inputs()

    def crash(point: str) -> None:
        if point == "publish.canonical.replace":
            os._exit(23)

    publisher = GenerationPublisher(root, fault_injector=crash)
    if operation == "single":
        publisher.publish("gen-interrupted-single", module, pack)
    else:
        publisher.publish_generation(
            "gen-interrupted-batch", ((module, pack),)
        )


def _acquire_lock_in_child(root: str, contended, acquired) -> None:
    from knowledge_compiler.storage.lifecycle import repository_lifecycle_lock

    with repository_lifecycle_lock(root, contention_hook=contended.set):
        acquired.set()


def _crash_while_holding_lock(root: str, acquired) -> None:
    from knowledge_compiler.storage.lifecycle import repository_lifecycle_lock

    with repository_lifecycle_lock(root):
        acquired.set()
        os._exit(23)


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


def _prepare_pending_lifecycle(root: Path) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher
    from knowledge_compiler.storage.lifecycle import save_latest_plan

    module, pack = _verified_inputs()
    save_latest_plan(root, _plan(), _run())
    GenerationPublisher(root).publish_generation(
        "gen-pending-transaction",
        ((module, pack),),
        observed_snapshot=_snapshot(root),
        pending_targets=(),
    )


def _pending_lifecycle_bytes(root: Path) -> tuple[bytes | None, bytes, bytes]:
    pending_path = root / ".knowledge/state/pending-targets.json"
    return (
        pending_path.read_bytes() if pending_path.exists() else None,
        (root / ".knowledge/plan.yaml").read_bytes(),
        (root / ".knowledge/manifest.yaml").read_bytes(),
    )


def _interrupt_pending_lifecycle(root: Path, failure_point: str) -> None:
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget

    _prepare_pending_lifecycle(root)

    def crash(point: str) -> None:
        if point == failure_point:
            raise _SimulatedProcessDeath(point)

    store = PendingStore(
        root / ".knowledge/state/pending-targets.json",
        fault_injector=crash,
    )
    with pytest.raises(_SimulatedProcessDeath, match=failure_point):
        store.add(
            PersistedTarget(target_id="module.lifecycle.alpha", reason="retry")
        )


def _assert_newer_generation_survives_pending_store_reload(
    root: Path, generation: str
) -> None:
    from knowledge_compiler.incremental.pending import PendingStore

    manifest_path = root / ".knowledge/manifest.yaml"
    committed = manifest_path.read_bytes()
    manifest = yaml.safe_load(committed)
    assert manifest["active_generation"] == generation
    assert manifest["observed_snapshot"]["commit"] == "commit-two"

    PendingStore(root / ".knowledge/state/pending-targets.json")
    assert manifest_path.read_bytes() == committed
    assert not (
        root / ".knowledge/state/pending-lifecycle-transaction.json"
    ).exists()


def _assert_generation_interval_blocks_pending_process(
    root: Path, operation: str
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher

    _prepare_pending_lifecycle(root)
    module, pack = _verified_inputs()
    newer_generation = f"gen-newer-raced-{operation}"
    newer_snapshot = _snapshot(root, commit="commit-two")
    if operation == "recover":
        GenerationPublisher(root).publish_generation(
            newer_generation,
            ((module, pack),),
            observed_snapshot=newer_snapshot,
        )

    publisher = GenerationPublisher(root)
    recovered = threading.Event()
    continue_generation = threading.Event()
    original_recovery = publisher._recover_pending_lifecycle

    def pause_after_recovery() -> None:
        original_recovery()
        recovered.set()
        if not continue_generation.wait(timeout=10):
            raise AssertionError("generation test pause timed out")

    publisher._recover_pending_lifecycle = pause_after_recovery
    publisher_errors: list[BaseException] = []

    def run_generation() -> None:
        try:
            if operation == "single":
                publisher.publish(
                    newer_generation,
                    module,
                    pack,
                    observed_snapshot=newer_snapshot,
                )
            elif operation == "batch":
                publisher.publish_generation(
                    newer_generation,
                    ((module, pack),),
                    observed_snapshot=newer_snapshot,
                )
            else:
                publisher.recover()
        except BaseException as error:
            publisher_errors.append(error)

    context = multiprocessing.get_context("fork")
    start_pending = context.Event()
    lock_contended = context.Event()
    pending_finished = context.Event()
    pending_process = context.Process(
        target=_crash_pending_in_child,
        args=(
            str(root),
            start_pending,
            lock_contended,
            pending_finished,
        ),
    )
    pending_process.start()
    publisher_thread = threading.Thread(target=run_generation)
    publisher_thread.start()
    assert recovered.wait(timeout=10)
    start_pending.set()
    contention_observed = lock_contended.wait(timeout=2)
    finished_while_generation_paused = pending_finished.is_set()
    continue_generation.set()
    publisher_thread.join(timeout=10)
    pending_process.join(timeout=10)

    assert not publisher_thread.is_alive()
    assert not pending_process.is_alive()
    assert pending_process.exitcode == 0
    assert publisher_errors == []
    assert contention_observed is True
    assert finished_while_generation_paused is False

    manifest_path = root / ".knowledge/manifest.yaml"
    before_pending_recovery = yaml.safe_load(manifest_path.read_bytes())
    assert before_pending_recovery["active_generation"] == newer_generation
    assert before_pending_recovery["observed_snapshot"]["commit"] == "commit-two"
    from knowledge_compiler.incremental.pending import PendingStore

    PendingStore(root / ".knowledge/state/pending-targets.json")
    after_pending_recovery = yaml.safe_load(manifest_path.read_bytes())
    assert after_pending_recovery["active_generation"] == newer_generation
    assert after_pending_recovery["observed_snapshot"]["commit"] == "commit-two"
    assert not (
        root / ".knowledge/state/pending-lifecycle-transaction.json.tmp"
    ).exists()


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


@pytest.mark.parametrize("failure_point", _PENDING_TRANSACTION_FAILURE_POINTS)
def test_pending_lifecycle_exception_never_returns_split_brain(
    tmp_path: Path, failure_point: str
) -> None:
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget
    from knowledge_compiler.storage.lifecycle import LifecycleWriteError

    root = tmp_path / "subject"
    expected_root = tmp_path / "expected"
    _prepare_pending_lifecycle(root)
    _prepare_pending_lifecycle(expected_root)
    old_bytes = _pending_lifecycle_bytes(root)
    PendingStore(
        expected_root / ".knowledge/state/pending-targets.json"
    ).add(PersistedTarget(target_id="module.lifecycle.alpha", reason="retry"))
    new_bytes = _pending_lifecycle_bytes(expected_root)

    def fail(point: str) -> None:
        if point == failure_point:
            raise OSError(f"injected at {point}")

    store = PendingStore(
        root / ".knowledge/state/pending-targets.json",
        fault_injector=fail,
    )
    with pytest.raises(LifecycleWriteError, match=failure_point):
        store.add(
            PersistedTarget(target_id="module.lifecycle.alpha", reason="retry")
        )

    assert _pending_lifecycle_bytes(root) in {old_bytes, new_bytes}
    assert not (
        root / ".knowledge/state/pending-lifecycle-transaction.json"
    ).exists()
    assert not (
        root / ".knowledge/state/pending-lifecycle-transaction.json.tmp"
    ).exists()


@pytest.mark.parametrize("failure_point", _PENDING_TRANSACTION_FAILURE_POINTS)
def test_pending_lifecycle_restart_recovers_all_old_or_all_new_bytes(
    tmp_path: Path, failure_point: str
) -> None:
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget

    root = tmp_path / "subject"
    expected_root = tmp_path / "expected"
    _prepare_pending_lifecycle(root)
    _prepare_pending_lifecycle(expected_root)
    old_bytes = _pending_lifecycle_bytes(root)
    PendingStore(
        expected_root / ".knowledge/state/pending-targets.json"
    ).add(PersistedTarget(target_id="module.lifecycle.alpha", reason="retry"))
    new_bytes = _pending_lifecycle_bytes(expected_root)

    def crash(point: str) -> None:
        if point == failure_point:
            raise _SimulatedProcessDeath(point)

    store = PendingStore(
        root / ".knowledge/state/pending-targets.json",
        fault_injector=crash,
    )
    with pytest.raises(_SimulatedProcessDeath, match=failure_point):
        store.add(
            PersistedTarget(target_id="module.lifecycle.alpha", reason="retry")
        )

    PendingStore(root / ".knowledge/state/pending-targets.json")
    assert _pending_lifecycle_bytes(root) in {old_bytes, new_bytes}
    assert not (
        root / ".knowledge/state/pending-lifecycle-transaction.json"
    ).exists()
    assert not (
        root / ".knowledge/state/pending-lifecycle-transaction.json.tmp"
    ).exists()


@pytest.mark.parametrize("failure_point", _PENDING_TRANSACTION_FAILURE_POINTS)
def test_single_generation_recovers_pending_journal_before_newer_manifest(
    tmp_path: Path, failure_point: str
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher

    _interrupt_pending_lifecycle(tmp_path, failure_point)
    module, pack = _verified_inputs()
    generation = "gen-newer-single"

    GenerationPublisher(tmp_path).publish(
        generation,
        module,
        pack,
        observed_snapshot=_snapshot(tmp_path, commit="commit-two"),
    )

    _assert_newer_generation_survives_pending_store_reload(
        tmp_path, generation
    )


@pytest.mark.parametrize("failure_point", _PENDING_TRANSACTION_FAILURE_POINTS)
def test_batch_generation_recovers_pending_journal_before_newer_manifest(
    tmp_path: Path, failure_point: str
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher

    _interrupt_pending_lifecycle(tmp_path, failure_point)
    module, pack = _verified_inputs()
    generation = "gen-newer-batch"

    GenerationPublisher(tmp_path).publish_generation(
        generation,
        ((module, pack),),
        observed_snapshot=_snapshot(tmp_path, commit="commit-two"),
    )

    _assert_newer_generation_survives_pending_store_reload(
        tmp_path, generation
    )


def test_generation_recovery_also_completes_pending_lifecycle_journal(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.storage import GenerationPublisher

    _interrupt_pending_lifecycle(
        tmp_path, "pending-lifecycle.plan.replace"
    )

    GenerationPublisher(tmp_path).recover()

    manifest = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["active_generation"] == "gen-pending-transaction"
    assert manifest["pending_targets"] == ["module.lifecycle.alpha"]
    assert not (
        tmp_path / ".knowledge/state/pending-lifecycle-transaction.json"
    ).exists()


def test_single_generation_lock_blocks_cross_process_pending_mutation(
    tmp_path: Path,
) -> None:
    _assert_generation_interval_blocks_pending_process(tmp_path, "single")


def test_batch_generation_lock_blocks_cross_process_pending_mutation(
    tmp_path: Path,
) -> None:
    _assert_generation_interval_blocks_pending_process(tmp_path, "batch")


def test_generation_recovery_lock_blocks_cross_process_pending_mutation(
    tmp_path: Path,
) -> None:
    _assert_generation_interval_blocks_pending_process(tmp_path, "recover")


@pytest.mark.parametrize("operation", ("single", "batch"))
def test_pending_mutation_recovers_interrupted_generation_before_projection(
    tmp_path: Path, operation: str
) -> None:
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget
    from knowledge_compiler.storage import GenerationPublisher

    _prepare_pending_lifecycle(tmp_path)
    context = multiprocessing.get_context("fork")
    process = context.Process(
        target=_crash_generation_in_child,
        args=(str(tmp_path), operation),
    )
    process.start()
    process.join(timeout=10)
    assert not process.is_alive()
    assert process.exitcode == 23
    transactions = tmp_path / ".knowledge/state/transactions"
    assert any(transactions.iterdir())

    PendingStore(tmp_path / ".knowledge/state/pending-targets.json").add(
        PersistedTarget(target_id="module.lifecycle.alpha", reason="retry")
    )

    assert not any(transactions.iterdir())
    committed = _pending_lifecycle_bytes(tmp_path)
    GenerationPublisher(tmp_path).recover()
    assert _pending_lifecycle_bytes(tmp_path) == committed
    manifest = yaml.safe_load(committed[2])
    plan = yaml.safe_load(committed[1])
    assert manifest["pending_targets"] == ["module.lifecycle.alpha"]
    assert next(
        item for item in plan["targets"]
        if item["target_id"] == "module.lifecycle.alpha"
    )["pending"] is True


def test_manifest_lifecycle_writer_cannot_replace_newer_generation(
    tmp_path: Path, monkeypatch
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher
    from knowledge_compiler.storage import lifecycle

    _prepare_pending_lifecycle(tmp_path)
    writer_paused = threading.Event()
    continue_writer = threading.Event()
    publication_contended = threading.Event()
    writer_errors: list[BaseException] = []
    publisher_errors: list[BaseException] = []
    monkeypatch.setattr(
        lifecycle,
        "_LOCK_CONTENTION_HOOK",
        publication_contended.set,
        raising=False,
    )

    def pause_writer(point: str) -> None:
        if point == "manifest-lifecycle.stage.write":
            writer_paused.set()
            if not continue_writer.wait(timeout=10):
                raise AssertionError("manifest writer pause timed out")

    def write_lifecycle() -> None:
        try:
            lifecycle.update_manifest_lifecycle(
                tmp_path,
                pending_targets=("module.lifecycle.alpha",),
                fault_injector=pause_writer,
            )
        except BaseException as error:
            writer_errors.append(error)

    module, pack = _verified_inputs()

    def publish() -> None:
        try:
            GenerationPublisher(tmp_path).publish_generation(
                "gen-new-after-lifecycle-writer", ((module, pack),)
            )
        except BaseException as error:
            publisher_errors.append(error)

    writer = threading.Thread(target=write_lifecycle)
    publisher = threading.Thread(target=publish)
    writer.start()
    assert writer_paused.wait(timeout=10)
    publisher.start()
    contention_observed = publication_contended.wait(timeout=2)
    continue_writer.set()
    writer.join(timeout=10)
    publisher.join(timeout=10)

    assert not writer.is_alive()
    assert not publisher.is_alive()
    assert writer_errors == []
    assert publisher_errors == []
    assert contention_observed is True
    manifest = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["active_generation"] == "gen-new-after-lifecycle-writer"
    assert manifest["pending_targets"] == ["module.lifecycle.alpha"]


def test_repository_lifecycle_lock_normalizes_supported_root_aliases(
    tmp_path: Path, monkeypatch
) -> None:
    from knowledge_compiler.storage.lifecycle import repository_lifecycle_lock

    repository = tmp_path / "repository"
    (repository / ".knowledge").mkdir(parents=True)
    linked = tmp_path / "linked"
    linked.symlink_to(repository, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    aliases = (
        repository / ".knowledge",
        Path("repository"),
        linked / ".knowledge",
    )
    context = multiprocessing.get_context("fork")
    for alias in aliases:
        contended = context.Event()
        acquired = context.Event()
        with repository_lifecycle_lock(repository):
            process = context.Process(
                target=_acquire_lock_in_child,
                args=(str(alias), contended, acquired),
            )
            process.start()
            contention_observed = contended.wait(timeout=2)
            acquired_while_held = acquired.is_set()
        process.join(timeout=10)
        assert not process.is_alive()
        assert process.exitcode == 0
        assert contention_observed is True
        assert acquired_while_held is False
        assert acquired.is_set()


def test_generation_publisher_normalizes_knowledge_root_alias(
    tmp_path: Path,
) -> None:
    from test_generation_publication import _verified_inputs

    from knowledge_compiler.storage import GenerationPublisher

    module, pack = _verified_inputs()
    knowledge = tmp_path / ".knowledge"
    GenerationPublisher(knowledge).publish_generation(
        "gen-knowledge-root-alias", ((module, pack),)
    )

    assert (knowledge / "manifest.yaml").is_file()
    assert not (knowledge / ".knowledge").exists()


def test_repository_lifecycle_lock_rejects_public_namespace(
    tmp_path: Path, monkeypatch
) -> None:
    import tempfile

    from knowledge_compiler.storage.lifecycle import (
        LifecycleWriteError,
        repository_lifecycle_lock,
    )

    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary_root))
    lock_root = temporary_root / f"codewiki-lifecycle-{os.geteuid()}"
    lock_root.mkdir(mode=0o700)
    lock_root.chmod(0o777)

    with pytest.raises(LifecycleWriteError, match="permissions"):
        with repository_lifecycle_lock(tmp_path / "repository"):
            raise AssertionError("public lock namespace must be rejected")


def test_repository_lifecycle_lock_rejects_foreign_namespace_owner(
    tmp_path: Path, monkeypatch
) -> None:
    import tempfile

    from knowledge_compiler.storage.lifecycle import (
        LifecycleWriteError,
        repository_lifecycle_lock,
    )

    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()
    effective_user = os.geteuid() + 1
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary_root))
    monkeypatch.setattr(os, "geteuid", lambda: effective_user)
    (temporary_root / f"codewiki-lifecycle-{effective_user}").mkdir(mode=0o700)

    with pytest.raises(LifecycleWriteError, match="owner"):
        with repository_lifecycle_lock(tmp_path / "repository"):
            raise AssertionError("foreign lock namespace must be rejected")


def test_repository_lifecycle_lock_rejects_public_lock_file(
    tmp_path: Path, monkeypatch
) -> None:
    import hashlib
    import tempfile

    from knowledge_compiler.storage.lifecycle import (
        LifecycleWriteError,
        repository_lifecycle_lock,
    )

    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary_root))
    lock_root = temporary_root / f"codewiki-lifecycle-{os.geteuid()}"
    lock_root.mkdir(mode=0o700)
    repository_key = hashlib.sha256(
        str((tmp_path / "repository").resolve()).encode("utf-8")
    ).hexdigest()
    lock_file = lock_root / f"{repository_key}.lock"
    lock_file.write_bytes(b"")
    lock_file.chmod(0o666)

    with pytest.raises(LifecycleWriteError, match="permissions"):
        with repository_lifecycle_lock(tmp_path / "repository"):
            raise AssertionError("public lock file must be rejected")


def test_repository_lifecycle_lock_is_released_by_process_death(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.storage.lifecycle import repository_lifecycle_lock

    context = multiprocessing.get_context("fork")
    acquired = context.Event()
    process = context.Process(
        target=_crash_while_holding_lock,
        args=(str(tmp_path), acquired),
    )
    process.start()
    assert acquired.wait(timeout=10)
    process.join(timeout=10)
    assert not process.is_alive()
    assert process.exitcode == 23

    contention_points: list[str] = []
    with repository_lifecycle_lock(
        tmp_path,
        contention_hook=lambda: contention_points.append("contended"),
    ):
        pass
    assert contention_points == []


def test_locked_recovery_helpers_do_not_reacquire_repository_lock(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.storage.generation import (
        _recover_generation_transactions_locked,
    )
    from knowledge_compiler.storage.lifecycle import (
        _recover_pending_lifecycle_locked,
        repository_lifecycle_lock,
    )

    contention_points: list[str] = []
    with repository_lifecycle_lock(
        tmp_path,
        contention_hook=lambda: contention_points.append("contended"),
    ):
        assert _recover_pending_lifecycle_locked(tmp_path) is False
        assert _recover_generation_transactions_locked(tmp_path) is False
    assert contention_points == []


def test_repository_lifecycle_lock_rejects_symlink_file(
    tmp_path: Path, monkeypatch
) -> None:
    import hashlib
    import os
    import tempfile

    from knowledge_compiler.storage.lifecycle import (
        LifecycleWriteError,
        repository_lifecycle_lock,
    )

    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary_root))
    lock_root = temporary_root / f"codewiki-lifecycle-{os.geteuid()}"
    lock_root.mkdir(mode=0o700)
    repository_key = hashlib.sha256(
        str((tmp_path / "repository").resolve()).encode("utf-8")
    ).hexdigest()
    decoy = tmp_path / "decoy.lock"
    decoy.write_bytes(b"keep exact")
    (lock_root / f"{repository_key}.lock").symlink_to(decoy)

    with pytest.raises(LifecycleWriteError, match="symlink"):
        with repository_lifecycle_lock(tmp_path / "repository"):
            raise AssertionError("unsafe lock must never be acquired")

    assert decoy.read_bytes() == b"keep exact"


def test_pending_lifecycle_rejects_manifest_temp_symlink_before_mutation(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget
    from knowledge_compiler.storage.lifecycle import LifecycleWriteError

    _prepare_pending_lifecycle(tmp_path)
    old_bytes = _pending_lifecycle_bytes(tmp_path)
    decoy = tmp_path / "decoy.yaml"
    decoy.write_bytes(b"keep: exact\n")
    (tmp_path / ".knowledge/manifest.yaml.tmp").symlink_to(decoy)

    with pytest.raises(LifecycleWriteError, match="symlink"):
        PendingStore(
            tmp_path / ".knowledge/state/pending-targets.json"
        ).add(PersistedTarget(target_id="module.lifecycle.alpha", reason="retry"))

    assert _pending_lifecycle_bytes(tmp_path) == old_bytes
    assert decoy.read_bytes() == b"keep: exact\n"


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
