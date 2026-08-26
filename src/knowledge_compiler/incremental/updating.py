from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from knowledge_compiler.config import KnowledgeConfig
from knowledge_compiler.incremental.invalidation import (
    InvalidationError,
    invalidate_changed_knowledge,
    load_generation_knowledge,
)
from knowledge_compiler.incremental.pending import PendingStore
from knowledge_compiler.repository.changes import ChangeSet, compute_changes
from knowledge_compiler.repository.inventory import (
    FileRecord,
    load_baseline,
    save_baseline,
)
from knowledge_compiler.repository.local_git import LocalGitRepositoryProvider


@dataclass(frozen=True)
class IncrementalUpdateOutcome:
    status: Literal["complete", "partial", "failed"]
    change_set: ChangeSet
    full_refresh: bool
    refresh_reason: str | None
    invalidation_generation: str | None
    stale_object_ids: tuple[str, ...]
    pending_target_ids: tuple[str, ...]
    generation: str | None
    published_object_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]


BuildRunner = Callable[..., Any]


def run_incremental_update(
    *,
    repository_root: Path,
    executor: Literal["llm", "agent"],
    config: KnowledgeConfig,
    build_runner: BuildRunner | None = None,
) -> IncrementalUpdateOutcome:
    """Detect before provider sync, invalidate safely, then regenerate."""

    root = Path(repository_root).resolve()
    current = _inventory(root)
    baseline_path = root / ".knowledge/baseline/eligible-files.json"
    baseline, full_refresh, refresh_reason = _baseline(baseline_path)
    change_set = compute_changes(baseline, current)
    manifest_exists = (root / ".knowledge/manifest.yaml").is_file()
    pending = PendingStore(root / ".knowledge/state/pending-targets.json")
    pending_before = pending.target_ids()

    if (
        not full_refresh
        and change_set.is_empty()
        and not pending_before
        and manifest_exists
    ):
        return IncrementalUpdateOutcome(
            status="complete",
            change_set=change_set,
            full_refresh=False,
            refresh_reason=None,
            invalidation_generation=None,
            stale_object_ids=(),
            pending_target_ids=(),
            generation=None,
            published_object_ids=(),
            diagnostics=("no eligible changes or pending targets",),
        )

    invalidation_generation = None
    stale_ids: tuple[str, ...] = ()
    if manifest_exists and not change_set.is_empty():
        try:
            invalidated = invalidate_changed_knowledge(
                repository_root=root, change_set=change_set
            )
        except InvalidationError as error:
            return _failed(
                change_set,
                full_refresh,
                refresh_reason,
                f"safe invalidation failed: {error}",
                pending,
            )
        invalidation_generation = invalidated.generation
        stale_ids = invalidated.stale
        pending = PendingStore(
            root / ".knowledge/state/pending-targets.json"
        )

    if build_runner is None:
        from knowledge_compiler.building import run_configured_build

        build_runner = run_configured_build
    target_ids: frozenset[str] | None = None
    preserved_items: tuple[tuple[object, object | None], ...] = ()
    if manifest_exists and not full_refresh:
        selected = set(stale_ids) | pending.target_ids()
        if selected:
            try:
                objects, packs = load_generation_knowledge(root)
            except InvalidationError as error:
                return _failed(
                    change_set,
                    full_refresh,
                    refresh_reason,
                    f"selective generation state failed: {error}",
                    pending,
                )
            target_ids = frozenset(selected)
            preserved_items = tuple(
                (canonical, packs.get(object_id))
                for object_id, canonical in sorted(objects.items())
                if object_id not in selected
                and canonical.validity.status == "verified"
            )
    try:
        built = build_runner(
            repository_root=root,
            executor=executor,
            config=config,
            target_ids=target_ids,
            preserved_items=preserved_items,
        )
    except (OSError, RuntimeError, ValueError) as error:
        if stale_ids:
            save_baseline(baseline_path, current)
            return IncrementalUpdateOutcome(
                status="partial",
                change_set=change_set,
                full_refresh=full_refresh,
                refresh_reason=refresh_reason,
                invalidation_generation=invalidation_generation,
                stale_object_ids=stale_ids,
                pending_target_ids=tuple(sorted(pending.target_ids())),
                generation=None,
                published_object_ids=(),
                diagnostics=(f"regeneration failed: {error}",),
            )
        return _failed(
            change_set,
            full_refresh,
            refresh_reason,
            f"regeneration failed: {error}",
            pending,
        )

    published_ids = tuple(built.published_object_ids)
    for target_id in published_ids:
        pending.resolve(target_id)
    remaining = tuple(sorted(pending.target_ids()))
    status = built.status
    diagnostics = tuple(built.diagnostics)
    if status == "complete" and remaining:
        status = "partial"
        diagnostics += ("pending targets remain after regeneration",)
    if status == "failed" and manifest_exists and stale_ids:
        status = "partial"
    if status == "partial" and not manifest_exists and built.generation is None:
        status = "failed"

    if status == "complete" or stale_ids:
        # Once safe invalidation commits, the observed baseline advances even
        # if semantic regeneration remains pending; the pending store carries
        # retry intent into the next no-diff update.
        save_baseline(baseline_path, current)

    return IncrementalUpdateOutcome(
        status=status,
        change_set=change_set,
        full_refresh=full_refresh,
        refresh_reason=refresh_reason,
        invalidation_generation=invalidation_generation,
        stale_object_ids=stale_ids,
        pending_target_ids=remaining,
        generation=built.generation,
        published_object_ids=published_ids,
        diagnostics=diagnostics,
    )


def _inventory(root: Path) -> tuple[FileRecord, ...]:
    return tuple(
        FileRecord(
            path=record.path,
            blob_id=record.blob_id,
            content_hash=record.content_hash,
            size=record.size,
            language=record.language,
        )
        for record in LocalGitRepositoryProvider().inventory(root)
        if record.supported
    )


def _baseline(
    path: Path,
) -> tuple[tuple[FileRecord, ...], bool, str | None]:
    if not path.exists():
        return (), True, "baseline_missing"
    try:
        return load_baseline(path), False, None
    except ValueError:
        return (), True, "baseline_corrupt"


def _failed(
    change_set: ChangeSet,
    full_refresh: bool,
    refresh_reason: str | None,
    diagnostic: str,
    pending: PendingStore,
) -> IncrementalUpdateOutcome:
    return IncrementalUpdateOutcome(
        status="failed",
        change_set=change_set,
        full_refresh=full_refresh,
        refresh_reason=refresh_reason,
        invalidation_generation=None,
        stale_object_ids=(),
        pending_target_ids=tuple(sorted(pending.target_ids())),
        generation=None,
        published_object_ids=(),
        diagnostics=(diagnostic,),
    )


__all__ = ["IncrementalUpdateOutcome", "run_incremental_update"]
