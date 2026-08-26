from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from knowledge_compiler.contracts.planning import KnowledgePlan
from knowledge_compiler.contracts.repository import NonBlankString, RepositorySnapshot
from knowledge_compiler.orchestrator.contracts import (
    RunRecord,
    TargetState,
    TerminalResult,
)


_MAX_TRACKED_YAML_BYTES = 1_000_000
_NON_BLANK = TypeAdapter(NonBlankString)
_TARGET_IDS = TypeAdapter(tuple[NonBlankString, ...])
FaultInjector = Callable[[str], None]
KnowledgeObjectType = Literal[
    "module", "architecture", "flow", "rule", "tech-stack"
]


class LifecycleWriteError(RuntimeError):
    """Raised when tracked lifecycle state cannot be written safely."""


@contextmanager
def repository_lifecycle_lock(
    root: str | os.PathLike[str],
) -> Iterator[None]:
    """Serialize lifecycle and generation transactions across processes."""

    temporary_root = Path(tempfile.gettempdir()).resolve()
    _ensure_safe_parent(temporary_root)
    lock_root = temporary_root / f"codewiki-lifecycle-{os.getuid()}"
    try:
        lock_root.mkdir(mode=0o700)
    except FileExistsError:
        if lock_root.is_symlink() or not lock_root.is_dir():
            raise LifecycleWriteError(
                f"lifecycle lock directory is unsafe: {lock_root}"
            )
    repository_key = hashlib.sha256(
        str(Path(root).resolve()).encode("utf-8")
    ).hexdigest()
    lock_path = lock_root / f"{repository_key}.lock"
    _reject_unsafe_file(lock_path)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise LifecycleWriteError(
            f"lifecycle lock cannot be opened: {error}"
        ) from error
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise LifecycleWriteError(
                f"lifecycle lock is not a regular file: {lock_path}"
            )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


class ObservedSnapshotProjection(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    repository_id: NonBlankString
    snapshot_id: NonBlankString
    commit: NonBlankString
    dirty: bool
    working_tree_hash: NonBlankString | None = None

    @classmethod
    def from_snapshot(
        cls, snapshot: RepositorySnapshot | ObservedSnapshotProjection | object
    ) -> ObservedSnapshotProjection:
        if isinstance(snapshot, ObservedSnapshotProjection):
            return cls.model_validate(snapshot.model_dump(mode="json"))
        validated = RepositorySnapshot.model_validate(
            snapshot.model_dump(mode="json")
        )
        return cls(
            repository_id=validated.repository_id,
            snapshot_id=validated.snapshot_id,
            commit=validated.commit,
            dirty=validated.dirty,
            working_tree_hash=validated.working_tree_hash,
        )


class LatestPlanTarget(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    target_id: NonBlankString
    object_type: KnowledgeObjectType
    required: bool
    priority: int = Field(strict=True, ge=1, le=9)
    state: TargetState
    result: TerminalResult | None = None
    published_object_id: NonBlankString | None = None
    attempt: int = Field(strict=True, gt=0)
    repair_attempts: int = Field(strict=True, ge=0)
    pending: bool = False

    @model_validator(mode="after")
    def validate_result_state(self) -> LatestPlanTarget:
        if self.state is TargetState.DONE and self.result is None:
            raise ValueError("done lifecycle targets require a result")
        if self.state is not TargetState.DONE and self.result is not None:
            raise ValueError("only done lifecycle targets carry a result")
        return self


class LatestPlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    schema_version: Literal["0.1"] = "0.1"
    run_id: NonBlankString
    repository_id: NonBlankString
    snapshot_id: NonBlankString
    executor: Literal["llm", "agent"]
    active: bool
    plan_attempt: int = Field(strict=True, gt=0)
    targets: tuple[LatestPlanTarget, ...]

    @model_validator(mode="after")
    def validate_unique_targets(self) -> LatestPlan:
        target_ids = [target.target_id for target in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("latest plan target ids must be unique")
        return self


def save_latest_plan(
    root: str | os.PathLike[str],
    plan: KnowledgePlan,
    run: RunRecord,
    *,
    fault_injector: FaultInjector | None = None,
) -> LatestPlan:
    """Atomically project run lifecycle state into tracked ``plan.yaml``."""

    validated_plan = KnowledgePlan.model_validate(plan.model_dump(mode="json"))
    validated_run = RunRecord.model_validate(run.model_dump(mode="json"))
    if (
        validated_plan.run_id != validated_run.run_id
        or validated_plan.repository_id != validated_run.repository_id
        or validated_plan.snapshot_id != validated_run.snapshot_id
    ):
        raise LifecycleWriteError("plan and run lifecycle identities differ")
    specs = {spec.target.id: spec for spec in validated_plan.targets}
    records = {record.target_id: record for record in validated_run.targets}
    if set(specs) != set(records):
        raise LifecycleWriteError("plan and run lifecycle target sets differ")
    pending = set(load_pending_target_ids(root))
    targets: list[LatestPlanTarget] = []
    for target_id in sorted(specs):
        spec = specs[target_id]
        record = records[target_id]
        if (
            spec.target.type != record.object_type
            or spec.required != record.required
            or spec.priority != record.priority
        ):
            raise LifecycleWriteError(
                f"plan and run target metadata differ: {target_id}"
            )
        targets.append(
            LatestPlanTarget(
                target_id=target_id,
                object_type=record.object_type,
                required=record.required,
                priority=record.priority,
                state=record.state,
                result=record.result,
                published_object_id=record.published_object_id,
                attempt=record.attempt,
                repair_attempts=record.repair_attempts,
                pending=target_id in pending,
            )
        )
    latest = LatestPlan(
        run_id=validated_run.run_id,
        repository_id=validated_run.repository_id,
        snapshot_id=validated_run.snapshot_id,
        executor=validated_run.executor,
        active=validated_run.active,
        plan_attempt=validated_plan.attempt,
        targets=tuple(targets),
    )
    _atomic_yaml(
        _knowledge_root(root) / "plan.yaml",
        latest.model_dump(mode="json"),
        label="plan",
        fault_injector=fault_injector,
    )
    return latest


def load_latest_plan(root: str | os.PathLike[str]) -> LatestPlan:
    path = _knowledge_root(root) / "plan.yaml"
    try:
        payload = yaml.safe_load(_read_regular(path))
        return LatestPlan.model_validate(payload)
    except LifecycleWriteError:
        raise
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise LifecycleWriteError(f"latest plan is unreadable: {error}") from error


def update_latest_plan_pending(
    root: str | os.PathLike[str], pending_target_ids: Iterable[str]
) -> bool:
    path = _knowledge_root(root) / "plan.yaml"
    if not os.path.lexists(path):
        return False
    updated = _latest_plan_with_pending(root, pending_target_ids)
    _atomic_yaml(path, updated.model_dump(mode="json"), label="plan")
    return True


def save_observed_snapshot_state(
    root: str | os.PathLike[str], snapshot: RepositorySnapshot
) -> ObservedSnapshotProjection:
    observed = ObservedSnapshotProjection.from_snapshot(snapshot)
    _atomic_yaml(
        _knowledge_root(root) / "state/observed-snapshot.yaml",
        observed.model_dump(mode="json"),
        label="observed-snapshot",
    )
    return observed


def load_observed_snapshot_state(
    root: str | os.PathLike[str],
) -> ObservedSnapshotProjection | None:
    path = _knowledge_root(root) / "state/observed-snapshot.yaml"
    if not os.path.lexists(path):
        return None
    try:
        return ObservedSnapshotProjection.model_validate(
            yaml.safe_load(_read_regular(path))
        )
    except LifecycleWriteError:
        raise
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise LifecycleWriteError(
            f"observed snapshot state is unreadable: {error}"
        ) from error


def load_pending_target_ids(root: str | os.PathLike[str]) -> tuple[str, ...]:
    path = _knowledge_root(root) / "state/pending-targets.json"
    if not os.path.lexists(path):
        return ()
    try:
        payload = json.loads(_read_regular(path))
        if not isinstance(payload, list):
            raise ValueError("pending store must be a list")
        return _validated_target_ids(item["target_id"] for item in payload)
    except LifecycleWriteError:
        raise
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise LifecycleWriteError(f"pending state is unreadable: {error}") from error


def manifest_lifecycle_fields(
    root: str | os.PathLike[str],
    *,
    observed_snapshot: RepositorySnapshot | ObservedSnapshotProjection | None = None,
    pending_targets: Iterable[str] | None = None,
) -> dict[str, object]:
    """Resolve explicit, staged, or previously committed manifest lifecycle."""

    knowledge = _knowledge_root(root)
    previous = _load_manifest_mapping(knowledge / "manifest.yaml")
    observed = (
        ObservedSnapshotProjection.from_snapshot(observed_snapshot)
        if observed_snapshot is not None
        else load_observed_snapshot_state(root)
    )
    if observed is None and previous is not None and "observed_snapshot" in previous:
        observed = ObservedSnapshotProjection.model_validate(
            previous["observed_snapshot"]
        )

    if pending_targets is not None:
        pending = _validated_target_ids(pending_targets)
    else:
        pending_path = knowledge / "state/pending-targets.json"
        if os.path.lexists(pending_path):
            pending = load_pending_target_ids(root)
        elif previous is not None and "pending_targets" in previous:
            pending = _validated_target_ids(previous["pending_targets"])
        elif observed is not None:
            pending = ()
        else:
            pending = None

    fields: dict[str, object] = {}
    if observed is not None:
        fields["observed_snapshot"] = observed.model_dump(mode="json")
    if pending is not None:
        fields["pending_targets"] = list(pending)
    return fields


def update_manifest_lifecycle(
    root: str | os.PathLike[str],
    *,
    observed_snapshot: RepositorySnapshot | ObservedSnapshotProjection | None = None,
    pending_targets: Iterable[str] | None = None,
    fault_injector: FaultInjector | None = None,
) -> bool:
    path = _knowledge_root(root) / "manifest.yaml"
    manifest = _load_manifest_mapping(path)
    if manifest is None:
        return False
    if observed_snapshot is None:
        fields: dict[str, object] = {}
        if pending_targets is not None:
            fields["pending_targets"] = list(
                _validated_target_ids(pending_targets)
            )
    else:
        fields = manifest_lifecycle_fields(
            root,
            observed_snapshot=observed_snapshot,
            pending_targets=pending_targets,
        )
    manifest.update(fields)
    _atomic_yaml(
        path,
        manifest,
        label="manifest-lifecycle",
        fault_injector=fault_injector,
    )
    return True


def commit_pending_lifecycle(
    root: str | os.PathLike[str],
    pending_targets: Iterable[object],
    *,
    fault_injector: FaultInjector | None = None,
) -> None:
    """Commit pending execution state and both tracked projections together."""

    with repository_lifecycle_lock(root):
        _commit_pending_lifecycle_locked(
            root,
            pending_targets,
            fault_injector=fault_injector,
        )


def _commit_pending_lifecycle_locked(
    root: str | os.PathLike[str],
    pending_targets: Iterable[object],
    *,
    fault_injector: FaultInjector | None = None,
) -> None:
    """Commit pending state while the repository lifecycle lock is held."""

    knowledge = _knowledge_root(root)
    _recover_pending_lifecycle_locked(root)
    payload = tuple(_pending_payload_item(target) for target in pending_targets)
    payload = tuple(sorted(payload, key=lambda item: item["target_id"]))
    target_ids = _validated_target_ids(item["target_id"] for item in payload)
    entries: list[tuple[str, Path, bytes]] = [
        (
            "pending",
            knowledge / "state/pending-targets.json",
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8"),
        )
    ]
    plan_path = knowledge / "plan.yaml"
    if os.path.lexists(plan_path):
        latest = _latest_plan_with_pending(root, target_ids)
        entries.append(
            (
                "plan",
                plan_path,
                serialize_tracked_yaml(latest.model_dump(mode="json")),
            )
        )
    manifest_path = knowledge / "manifest.yaml"
    if os.path.lexists(manifest_path):
        manifest = _load_manifest_mapping(manifest_path)
        assert manifest is not None
        manifest["pending_targets"] = list(target_ids)
        entries.append(
            ("manifest", manifest_path, serialize_tracked_yaml(manifest))
        )

    journal_path = knowledge / "state/pending-lifecycle-transaction.json"
    journal_temporary = journal_path.with_name(journal_path.name + ".tmp")
    _preflight_pending_transaction(entries, journal_path, journal_temporary)
    journal = {
        "schema_version": 1,
        "entries": [
            {
                "name": name,
                "data": base64.b64encode(data).decode("ascii"),
            }
            for name, _, data in entries
        ],
    }
    journal_bytes = (
        json.dumps(journal, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    inject = fault_injector or (lambda _point: None)
    try:
        _write_new_file(journal_temporary, journal_bytes)
        inject("pending-lifecycle.journal.replace")
        os.replace(journal_temporary, journal_path)
        inject("pending-lifecycle.journal.directory.fsync")
        _fsync_directory(journal_path.parent)
        for name, path, data in entries:
            _replace_pending_entry(path, data, name=name, inject=inject)
        journal_path.unlink()
        inject("pending-lifecycle.cleanup.directory.fsync")
        _fsync_directory(journal_path.parent)
    except Exception as error:
        try:
            _recover_pending_lifecycle_locked(root)
        except Exception as recovery_error:
            raise LifecycleWriteError(
                "pending lifecycle transaction and recovery failed: "
                f"{error}; recovery: {recovery_error}"
            ) from recovery_error
        if isinstance(error, LifecycleWriteError):
            raise
        raise LifecycleWriteError(
            f"pending lifecycle transaction failed at {error}"
        ) from error


def recover_pending_lifecycle(root: str | os.PathLike[str]) -> bool:
    """Replay an interrupted pending lifecycle transaction to all-new state."""

    with repository_lifecycle_lock(root):
        return _recover_pending_lifecycle_locked(root)


def _recover_pending_lifecycle_locked(root: str | os.PathLike[str]) -> bool:
    """Replay pending state while the repository lifecycle lock is held."""

    knowledge = _knowledge_root(root)
    journal_path = knowledge / "state/pending-lifecycle-transaction.json"
    journal_temporary = journal_path.with_name(journal_path.name + ".tmp")
    if not os.path.lexists(journal_path):
        if os.path.lexists(journal_temporary):
            _reject_unsafe_file(journal_temporary)
            journal_temporary.unlink()
        return False
    try:
        payload = json.loads(_read_regular(journal_path))
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported pending lifecycle journal schema")
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, list):
            raise ValueError("pending lifecycle journal entries are invalid")
        expected_paths = {
            "pending": knowledge / "state/pending-targets.json",
            "plan": knowledge / "plan.yaml",
            "manifest": knowledge / "manifest.yaml",
        }
        entries: list[tuple[str, Path, bytes]] = []
        names: set[str] = set()
        for raw in raw_entries:
            if not isinstance(raw, dict):
                raise ValueError("pending lifecycle journal entry is invalid")
            name = raw.get("name")
            encoded = raw.get("data")
            if name not in expected_paths or name in names or not isinstance(
                encoded, str
            ):
                raise ValueError("pending lifecycle journal identity is invalid")
            names.add(name)
            entries.append(
                (
                    name,
                    expected_paths[name],
                    base64.b64decode(encoded, validate=True),
                )
            )
        if (
            not names
            or names - {"pending", "plan", "manifest"}
            or "pending" not in names
        ):
            raise ValueError("pending lifecycle journal entry set is invalid")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise LifecycleWriteError(
            f"pending lifecycle journal is malformed: {error}"
        ) from error

    for name in ("pending", "plan", "manifest"):
        match = next((entry for entry in entries if entry[0] == name), None)
        if match is not None:
            _replace_pending_entry(
                match[1], match[2], name=name, inject=lambda _point: None
            )
    journal_path.unlink()
    _fsync_directory(journal_path.parent)
    if os.path.lexists(journal_temporary):
        _reject_unsafe_file(journal_temporary)
        journal_temporary.unlink()
    return True


def _validated_target_ids(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(_TARGET_IDS.validate_python(tuple(values)))))


def _pending_payload_item(target: object) -> dict[str, str]:
    if hasattr(target, "model_dump"):
        target = target.model_dump(mode="json")
    if not isinstance(target, dict) or set(target) != {"target_id", "reason"}:
        raise LifecycleWriteError("pending target payload is invalid")
    try:
        target_id = _NON_BLANK.validate_python(target["target_id"])
        reason = _NON_BLANK.validate_python(target["reason"])
    except ValueError as error:
        raise LifecycleWriteError("pending target payload is invalid") from error
    return {"target_id": target_id, "reason": reason}


def _latest_plan_with_pending(
    root: str | os.PathLike[str], pending_target_ids: Iterable[str]
) -> LatestPlan:
    latest = load_latest_plan(root)
    pending = set(_validated_target_ids(pending_target_ids))
    return latest.model_copy(
        update={
            "targets": tuple(
                target.model_copy(update={"pending": target.target_id in pending})
                for target in latest.targets
            )
        }
    )


def _knowledge_root(root: str | os.PathLike[str]) -> Path:
    path = Path(root).absolute()
    return path if path.name == ".knowledge" else path / ".knowledge"


def _load_manifest_mapping(path: Path) -> dict[str, object] | None:
    if not os.path.lexists(path):
        return None
    try:
        payload = yaml.safe_load(_read_regular(path))
    except LifecycleWriteError:
        raise
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise LifecycleWriteError(f"manifest is unreadable: {error}") from error
    if not isinstance(payload, dict):
        raise LifecycleWriteError("manifest must contain a mapping")
    return payload


def serialize_tracked_yaml(payload: object) -> bytes:
    data = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    ).encode("utf-8")
    if len(data) > _MAX_TRACKED_YAML_BYTES:
        raise LifecycleWriteError("tracked lifecycle YAML exceeds the size bound")
    return data


def _atomic_yaml(
    path: Path,
    payload: object,
    *,
    label: str,
    fault_injector: FaultInjector | None = None,
) -> None:
    inject = fault_injector or (lambda _point: None)
    data = serialize_tracked_yaml(payload)
    temporary = path.with_name(path.name + ".tmp")
    try:
        _ensure_safe_parent(path.parent)
        _reject_unsafe_file(path)
        if os.path.lexists(temporary):
            _reject_unsafe_file(temporary)
            temporary.unlink()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                inject(f"{label}.stage.write")
                stream.write(data)
                inject(f"{label}.stage.flush")
                stream.flush()
                inject(f"{label}.stage.fsync")
                os.fsync(stream.fileno())
        finally:
            os.close(fd)
        inject(f"{label}.replace")
        os.replace(temporary, path)
        inject(f"{label}.directory.fsync")
        _fsync_directory(path.parent)
    except Exception as error:
        if os.path.lexists(temporary) and not temporary.is_symlink():
            temporary.unlink(missing_ok=True)
        if isinstance(error, LifecycleWriteError):
            raise
        raise LifecycleWriteError(f"{label} write failed at {error}") from error


def _preflight_pending_transaction(
    entries: Iterable[tuple[str, Path, bytes]],
    journal_path: Path,
    journal_temporary: Path,
) -> None:
    paths = [path for _, path, _ in entries]
    paths.extend((journal_path, journal_temporary))
    for path in paths:
        _ensure_safe_parent(path.parent)
        _reject_unsafe_file(path)
    for _, path, _ in entries:
        temporary = path.with_name(path.name + ".tmp")
        if os.path.lexists(temporary):
            _reject_unsafe_file(temporary)
            temporary.unlink()
    if os.path.lexists(journal_temporary):
        _reject_unsafe_file(journal_temporary)
        journal_temporary.unlink()


def _replace_pending_entry(
    path: Path,
    data: bytes,
    *,
    name: str,
    inject: FaultInjector,
) -> None:
    temporary = path.with_name(path.name + ".tmp")
    _ensure_safe_parent(path.parent)
    _reject_unsafe_file(path)
    if os.path.lexists(temporary):
        _reject_unsafe_file(temporary)
        temporary.unlink()
    _write_new_file(temporary, data)
    inject(f"pending-lifecycle.{name}.replace")
    os.replace(temporary, path)
    inject(f"pending-lifecycle.{name}.directory.fsync")
    _fsync_directory(path.parent)


def _write_new_file(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def _ensure_safe_parent(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if os.path.lexists(current):
            if current.is_symlink() or not current.is_dir():
                raise LifecycleWriteError(
                    "managed lifecycle directory is a symlink or "
                    f"non-directory: {current}"
                )
        else:
            current.mkdir()


def _reject_unsafe_file(path: Path) -> None:
    if not os.path.lexists(path):
        return
    if path.is_symlink():
        raise LifecycleWriteError(f"managed lifecycle destination is a symlink: {path}")
    if not path.is_file():
        raise LifecycleWriteError(
            f"managed lifecycle destination is not a regular file: {path}"
        )


def _read_regular(path: Path) -> bytes:
    if path.is_symlink():
        raise LifecycleWriteError(f"managed lifecycle file is a symlink: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise LifecycleWriteError(
                f"managed lifecycle file is not regular: {path}"
            )
        with os.fdopen(fd, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = [
    "LatestPlan",
    "LatestPlanTarget",
    "LifecycleWriteError",
    "ObservedSnapshotProjection",
    "commit_pending_lifecycle",
    "load_latest_plan",
    "load_observed_snapshot_state",
    "load_pending_target_ids",
    "manifest_lifecycle_fields",
    "recover_pending_lifecycle",
    "repository_lifecycle_lock",
    "save_latest_plan",
    "save_observed_snapshot_state",
    "serialize_tracked_yaml",
    "update_latest_plan_pending",
    "update_manifest_lifecycle",
]
