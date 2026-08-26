from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from knowledge_compiler.compiler.markdown import _code, _text


UNAVAILABLE = "knowledge_update_required"
INDEX_PATH = ".knowledge/cache/knowledge-index.sqlite3"

_TYPE_BOOST = {"rule": 3.0, "flow": 2.0, "architecture": 1.0}
_TOKEN_CHARS = 4


class ContextRetrievalError(RuntimeError):
    """Raised when retrieval cannot prove a safe, current agent view."""


@dataclass(frozen=True)
class IndexBuildResult:
    generation: str
    verified_object_ids: tuple[str, ...]
    snapshot_commit: str
    index_path: Path


def build_knowledge_index(
    repository_root: Path, snapshot: object | None = None
) -> IndexBuildResult:
    """Rebuild the verified-only FTS index for the committed generation.

    The index is a deterministic projection of canonical state: every
    verified object becomes one searchable row plus its explicit
    relations; stale and non-canonical results never enter. The manifest
    generation stamps are recorded so retrieval can fail closed later.
    """

    root = Path(repository_root).resolve()
    from knowledge_compiler.compiler.wiki import _load_compile_inputs
    from knowledge_compiler.human.overlays import load_active_overlays
    from knowledge_compiler.retrieval import store

    try:
        manifest = yaml.safe_load(
            (root / ".knowledge/manifest.yaml").read_bytes()
        )
        objects, packs = _load_compile_inputs(root)
        overlays = load_active_overlays(root)
    except Exception as error:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: index inputs are unreadable: {error}"
        ) from error
    if not isinstance(manifest, dict):
        raise ContextRetrievalError(f"{UNAVAILABLE}: manifest is invalid")
    active = manifest.get("active_generation")
    agent_views = manifest.get("agent_views_generation")
    if not isinstance(active, str) or agent_views != active:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: generation stamps disagree with the manifest"
        )
    snapshot = _resolve_snapshot(root, snapshot)
    if snapshot.dirty:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: repository has uncommitted changes"
        )

    meta_rows = [
        ("active_generation", active),
        ("agent_views_generation", agent_views),
        ("snapshot_commit", snapshot.commit),
    ]
    object_rows: list[tuple[str, str, str, str]] = []
    relation_rows: list[tuple[str, str, str]] = []
    verified: list[str] = []
    for object_id, canonical in sorted(objects.items()):
        if canonical.validity.status != "verified":
            continue
        verified.append(object_id)
        overlay = overlays.get(object_id)
        body_parts = [
            canonical.title,
            canonical.summary.text,
            *[claim.statement for claim in canonical.claims],
            *_relation_text(canonical),
        ]
        if overlay is not None:
            body_parts.extend(
                [section.text for section in overlay.sections]
                + [note.text for note in overlay.notes]
            )
        body = "\n".join(body_parts)
        object_rows.append((object_id, canonical.type, canonical.title, body))
        relation_rows.extend(_relations_of(canonical))
    index_path = root / INDEX_PATH
    try:
        store.write_index(index_path, meta_rows, object_rows, relation_rows)
    except store.IndexStoreError as error:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: {error}"
        ) from error
    return IndexBuildResult(
        generation=active,
        verified_object_ids=tuple(sorted(verified)),
        snapshot_commit=snapshot.commit,
        index_path=index_path,
    )


def retrieve_task_context(
    repository_root: Path,
    task: str,
    *,
    budget: int = 6000,
    include_stale: bool = False,
    snapshot: object | None = None,
) -> str:
    """Compile budgeted, ranked task context from verified knowledge.

    Fails closed with ``knowledge_update_required`` unless the manifest
    stamps, the index stamps, and the repository snapshot all agree.
    """

    root = Path(repository_root).resolve()
    _require_current_view(root, snapshot)
    objects, packs = _load_objects_for_retrieval(root, include_stale)
    from knowledge_compiler.human.overlays import load_active_overlays
    from knowledge_compiler.retrieval import store

    overlays = load_active_overlays(root)
    index_path = root / INDEX_PATH
    try:
        ranks = store.match_objects(index_path, task)
    except store.IndexStoreError as error:
        raise ContextRetrievalError(f"{UNAVAILABLE}: {error}") from error
    ranked = sorted(
        ranks.items(),
        key=lambda item: (
            item[1] - _TYPE_BOOST.get(
                objects[item[0]].type if item[0] in objects else "", 0.0
            ),
            item[0],
        ),
    )
    one_hop: dict[str, str] = {}
    for object_id, _rank in ranked:
        try:
            relations = store.relations_of(index_path, object_id)
        except store.IndexStoreError as error:
            raise ContextRetrievalError(f"{UNAVAILABLE}: {error}") from error
        for target, predicate in relations:
            if target not in ranks and target in objects:
                one_hop.setdefault(target, f"{object_id} ({predicate})")

    lines = [
        "# Task context",
        "",
        f"query: {_text(task)}",
        f"budget: {budget} tokens (approximate)",
    ]
    if include_stale:
        lines.insert(
            2, "> [!WARNING] Diagnostic stale view — not safe coding context."
        )
    used = len("\n".join(lines)) // _TOKEN_CHARS
    included_ids: list[str] = []
    for object_id, _rank in ranked:
        canonical = objects.get(object_id)
        if canonical is None or canonical.validity.status != "verified":
            continue
        section = _object_section(
            object_id,
            canonical,
            packs.get(object_id),
            overlays.get(object_id),
            None,
        )
        cost = len(section) // _TOKEN_CHARS
        if included_ids and used + cost > budget:
            continue
        lines.append(section)
        used += cost
        included_ids.append(object_id)
    for object_id, via in sorted(one_hop.items()):
        canonical = objects.get(object_id)
        if canonical is None or canonical.validity.status != "verified":
            continue
        if object_id in included_ids:
            continue
        section = _object_section(
            object_id,
            canonical,
            packs.get(object_id),
            overlays.get(object_id),
            via,
        )
        cost = len(section) // _TOKEN_CHARS
        if used + cost > budget:
            continue
        lines.append(section)
        used += cost
        included_ids.append(object_id)
    if not included_ids and not include_stale:
        lines.extend(["", "_No verified knowledge matched the task._"])
    if include_stale:
        lines.extend(_stale_sections(objects))
    return "\n".join(lines) + "\n"


def _resolve_snapshot(root: Path, snapshot: object | None) -> object:
    if snapshot is not None:
        return snapshot
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
        RepositoryResolutionError,
    )

    try:
        return LocalGitRepositoryProvider().resolve(root)
    except (RepositoryResolutionError, OSError, ValueError) as error:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: repository snapshot is unresolvable: {error}"
        ) from error


def require_current_view(
    repository_root: Path, snapshot: object | None = None
) -> None:
    """Public gate for every default agent read (CLI and MCP)."""

    _require_current_view(Path(repository_root).resolve(), snapshot)


def _require_current_view(root: Path, snapshot: object | None) -> None:
    try:
        manifest = yaml.safe_load(
            (root / ".knowledge/manifest.yaml").read_bytes()
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: manifest unreadable: {error}"
        ) from error
    if not isinstance(manifest, dict):
        raise ContextRetrievalError(f"{UNAVAILABLE}: manifest is invalid")
    active = manifest.get("active_generation")
    agent_views = manifest.get("agent_views_generation")
    if not isinstance(active, str) or agent_views != active:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: agent views lag the active generation"
        )
    index_path = root / INDEX_PATH
    if not index_path.is_file():
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: verified retrieval index is missing; "
            "run knowledge compile"
        )
    from knowledge_compiler.retrieval import store

    try:
        meta = store.read_meta(index_path)
    except store.IndexStoreError as error:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: retrieval index is unreadable: {error}"
        ) from error
    if meta.get("active_generation") != active or meta.get(
        "agent_views_generation"
    ) != active:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: retrieval index lags the active generation; "
            "run knowledge compile"
        )
    current = _resolve_snapshot(root, snapshot)
    if current.dirty:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: repository has uncommitted changes"
        )
    if meta.get("snapshot_commit") != current.commit:
        raise ContextRetrievalError(
            f"{UNAVAILABLE}: repository snapshot moved past the index; "
            "run knowledge update"
        )


def _load_objects_for_retrieval(
    root: Path, include_stale: bool
) -> tuple[dict[str, object], dict[str, object]]:
    from knowledge_compiler.compiler.wiki import _load_compile_inputs

    objects, packs = _load_compile_inputs(root)
    if not include_stale:
        objects = {
            object_id: canonical
            for object_id, canonical in objects.items()
            if canonical.validity.status == "verified"
        }
    return objects, packs


def _object_section(
    object_id: str,
    canonical: object,
    pack: object | None,
    overlay: object | None,
    via: str | None,
) -> str:
    lines = [
        "",
        f"## {_text(canonical.title)}",
        "",
        f"- id: {_code(object_id)}",
        f"- type: {_code(canonical.type)}",
        f"- verified at: {_code(canonical.validity.verified_commit)}",
    ]
    if via is not None:
        lines.append(f"- related via: {_text(via)}")
    lines.extend(["", _text(canonical.summary.text), ""])
    if canonical.claims:
        lines.append("Key claims:")
        for claim in canonical.claims[:5]:
            lines.append(f"- {_text(claim.statement)}")
        lines.append("")
    relations = _relations_of(canonical)
    if relations:
        lines.append("Relations:")
        for _source, target, predicate in relations[:8]:
            lines.append(f"- {_text(predicate)} → {_code(target)}")
        lines.append("")
    if pack is not None:
        lines.append("Evidence pointers:")
        for item in sorted(
            pack.evidence, key=lambda e: (e.path, e.start_line)
        )[:8]:
            symbol = f" · {item.symbol}" if item.symbol else ""
            lines.append(
                f"- {_code(item.path)}{symbol} "
                f"L{item.start_line}-L{item.end_line}"
            )
        lines.append("")
    canonical_path = (
        ".knowledge/objects/"
        + _type_directory(canonical.type)
        + "/"
        + object_id
        + ".yaml"
    )
    lines.append(f"- canonical: {_code(canonical_path)}")
    if overlay is not None:
        lines.extend(["", "Human knowledge (source: human):"])
        for section in overlay.sections:
            lines.append(f"- [override/supplement] {_text(section.text)}")
        for note in overlay.notes:
            lines.append(f"- [note] {_text(note.text)}")
        lines.append("")
    return "\n".join(lines)


def _stale_sections(objects: dict[str, object]) -> list[str]:
    stale = sorted(
        (object_id, canonical)
        for object_id, canonical in objects.items()
        if canonical.validity.status == "stale"
    )
    if not stale:
        return ["", "_No stale objects are recorded._"]
    lines = ["", "## Stale objects (diagnostic only)", ""]
    for object_id, canonical in stale:
        lines.append(
            f"- {_code(object_id)} — reason: "
            f"{_text(canonical.validity.stale_reason or 'unknown')}; "
            f"last verified commit: "
            f"{_code(canonical.validity.verified_commit)}"
        )
    return lines


def _relations_of(canonical: object) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for field, default in (
        ("dependencies", "depends on"),
        ("relations", "relates to"),
    ):
        for item in getattr(canonical, field, ()) or ():
            target = getattr(item, "target", None)
            if isinstance(target, str):
                predicate = getattr(item, "predicate", None) or default
                rows.append((canonical.id, target, predicate))
    for target in getattr(canonical, "related_objects", ()) or ():
        if isinstance(target, str):
            rows.append((canonical.id, target, "related to"))
    for relationship in getattr(canonical, "relationships", ()) or ():
        target = getattr(relationship, "target", None)
        predicate = getattr(relationship, "predicate", "relates to")
        if isinstance(target, str):
            rows.append((canonical.id, target, predicate))
    return sorted(set(rows))


def _relation_text(canonical: object) -> list[str]:
    return [
        predicate for _source, _target, predicate in _relations_of(canonical)
    ]


def _type_directory(object_type: str) -> str:
    return {
        "module": "modules",
        "architecture": "architecture",
        "flow": "flows",
        "rule": "rules",
        "tech-stack": "tech-stack",
    }.get(object_type, "modules")


__all__ = [
    "ContextRetrievalError",
    "IndexBuildResult",
    "UNAVAILABLE",
    "build_knowledge_index",
    "require_current_view",
    "retrieve_task_context",
]
