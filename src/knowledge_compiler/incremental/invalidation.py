from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from knowledge_compiler.contracts.canonical import parse_canonical_knowledge
from knowledge_compiler.repository.changes import ChangeSet


@dataclass(frozen=True)
class InvalidationResult:
    stale: tuple[str, ...]
    healthy: tuple[str, ...]
    generation: str

    @property
    def has_stale(self) -> bool:
        return bool(self.stale)


def compute_affected(
    change_set: ChangeSet,
    evidence_paths: dict[str, tuple[str, ...]],
) -> set[str]:
    """Derive the set of object ids whose Evidence intersects the ChangeSet."""

    changed = set(change_set.added) | set(change_set.modified) | set(change_set.deleted)
    changed |= {old for old, _ in change_set.renamed}
    changed |= {new for _, new in change_set.renamed}
    affected: set[str] = set()
    for object_id, paths in evidence_paths.items():
        if changed & set(paths):
            affected.add(object_id)
    return affected


def merge_hints(local_affected: set[str], provider_hints: set[str]) -> set[str]:
    """Provider hints enrich local detection; they never replace it."""

    return set(local_affected) | set(provider_hints)


def mark_stale(
    canonical: Any, *, reason: str, evidence_path: str
) -> Any:
    """Mark a canonical object stale with a reason tied to its evidence."""

    stale_reason = f"{reason}: {evidence_path}"
    existing_reason = (
        canonical.validity.stale_reason
        if canonical.validity.stale_reason == stale_reason
        else stale_reason
    )
    return canonical.model_copy(
        update={
            "validity": canonical.validity.model_copy(
                update={"status": "stale", "stale_reason": existing_reason}
            )
        }
    )


class InvalidationError(RuntimeError):
    """Raised when safe invalidation cannot prove a complete generation."""


def invalidate_changed_knowledge(
    *, repository_root: Path, change_set: ChangeSet
) -> InvalidationResult:
    """Atomically mark affected canonicals stale and remove their Cards."""

    root = Path(repository_root).resolve()
    manifest_path = root / ".knowledge/manifest.yaml"
    try:
        manifest = yaml.safe_load(manifest_path.read_bytes())
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise InvalidationError(f"manifest unreadable: {error}") from error
    if not isinstance(manifest, dict) or not isinstance(
        manifest.get("active_generation"), str
    ):
        raise InvalidationError("no committed generation is available")
    objects = _load_manifest_objects(root, manifest)
    packs = _load_matching_evidence_packs(root, objects)
    evidence_paths = {
        object_id: tuple(item.path for item in pack.evidence)
        for object_id, pack in packs.items()
    }
    affected = compute_affected(change_set, evidence_paths)
    if not affected:
        return InvalidationResult(
            stale=(),
            healthy=tuple(sorted(objects)),
            generation=manifest["active_generation"],
        )

    changed_paths = _changed_paths(change_set)
    updated: dict[str, object] = {}
    for object_id, canonical in objects.items():
        if object_id not in affected:
            updated[object_id] = canonical
            continue
        evidence_path = next(
            path
            for path in evidence_paths[object_id]
            if path in changed_paths
        )
        updated[object_id] = mark_stale(
            canonical,
            reason=_reason_for(change_set, evidence_path),
            evidence_path=evidence_path,
        )

    items: list[tuple[object, object | None]] = []
    for object_id in sorted(updated):
        canonical = updated[object_id]
        pack = packs.get(object_id)
        if canonical.type == "module" and canonical.validity.status == "verified":
            if pack is None:
                raise InvalidationError(
                    f"verified module Evidence Pack unavailable: {object_id}"
                )
        items.append((canonical, pack))
    generation = _invalidation_generation(
        manifest["active_generation"], change_set
    )
    from knowledge_compiler.storage import GenerationPublisher, PublicationError

    try:
        GenerationPublisher(root).publish_generation(generation, tuple(items))
    except PublicationError as error:
        raise InvalidationError(str(error)) from error

    from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget

    pending = PendingStore(root / ".knowledge/state/pending-targets.json")
    for object_id in sorted(affected):
        pending.add(
            PersistedTarget(target_id=object_id, reason="evidence-changed")
        )
    return InvalidationResult(
        stale=tuple(sorted(affected)),
        healthy=tuple(sorted(set(objects) - affected)),
        generation=generation,
    )


def load_generation_knowledge(
    repository_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Load the manifest-bound canonical set and matching Evidence Packs."""

    root = Path(repository_root).resolve()
    try:
        manifest = yaml.safe_load(
            (root / ".knowledge/manifest.yaml").read_bytes()
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise InvalidationError(f"manifest unreadable: {error}") from error
    if not isinstance(manifest, dict):
        raise InvalidationError("manifest is invalid")
    objects = _load_manifest_objects(root, manifest)
    return objects, _load_matching_evidence_packs(root, objects)


_OBJECT_DIRECTORIES = {
    "architecture": "architecture",
    "module": "modules",
    "flow": "flows",
    "rule": "rules",
    "tech-stack": "tech-stack",
}


def _load_manifest_objects(root: Path, manifest: dict) -> dict[str, object]:
    inventory = manifest.get("objects")
    if not isinstance(inventory, list) or not inventory:
        raise InvalidationError("manifest object inventory is unavailable")
    loaded: dict[str, object] = {}
    for item in inventory:
        if not isinstance(item, dict) or item.get("type") not in _OBJECT_DIRECTORIES:
            raise InvalidationError("manifest object inventory is invalid")
        object_id = item.get("id")
        if not isinstance(object_id, str):
            raise InvalidationError("manifest object id is invalid")
        path = (
            root
            / ".knowledge/objects"
            / _OBJECT_DIRECTORIES[item["type"]]
            / f"{object_id}.yaml"
        )
        try:
            canonical = parse_canonical_knowledge(
                yaml.safe_load(path.read_bytes())
            )
        except (OSError, ValueError, yaml.YAMLError) as error:
            raise InvalidationError(
                f"canonical object unreadable: {object_id}: {error}"
            ) from error
        if canonical.id != object_id or canonical.type != item["type"]:
            raise InvalidationError("canonical object identity differs from manifest")
        loaded[object_id] = canonical
    return loaded


def _load_matching_evidence_packs(
    root: Path, objects: dict[str, object]
) -> dict[str, object]:
    from knowledge_compiler.contracts.evidence import EvidencePack

    packs: dict[str, object] = {}
    runs = root / ".knowledge/state/runs"
    if not runs.is_dir():
        return packs
    for path in sorted(runs.glob("*/targets/*/verified.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            canonical = parse_canonical_knowledge(payload["canonical"])
            pack = EvidencePack.model_validate(payload["evidence_pack"])
        except (KeyError, OSError, ValueError):
            continue
        current = objects.get(canonical.id)
        if current is None or not _same_verified_content(current, canonical):
            continue
        if pack.target.id == canonical.id:
            packs[canonical.id] = pack
    return packs


def _same_verified_content(current: object, historical: object) -> bool:
    if current.id != historical.id or current.type != historical.type:
        return False
    current_payload = current.model_dump(mode="json")
    historical_payload = historical.model_dump(mode="json")
    current_payload["validity"] = historical_payload.get("validity")
    return current_payload == historical_payload


def _changed_paths(change_set: ChangeSet) -> set[str]:
    paths = set(change_set.added) | set(change_set.modified) | set(change_set.deleted)
    paths |= {path for pair in change_set.renamed for path in pair}
    return paths


def _reason_for(change_set: ChangeSet, path: str) -> str:
    if path in change_set.deleted:
        return "source-deleted"
    if path in change_set.modified:
        return "source-modified"
    if any(path in pair for pair in change_set.renamed):
        return "source-renamed"
    return "source-added"


def _invalidation_generation(active_generation: str, change_set: ChangeSet) -> str:
    payload = json.dumps(
        [active_generation, change_set.model_dump(mode="json")],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "gen-invalidate-" + hashlib.sha256(payload).hexdigest()[:24]


__all__ = [
    "InvalidationResult",
    "InvalidationError",
    "compute_affected",
    "invalidate_changed_knowledge",
    "load_generation_knowledge",
    "mark_stale",
    "merge_hints",
]
