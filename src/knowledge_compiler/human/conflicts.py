from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from knowledge_compiler.human.overlays import load_active_overlays


@dataclass(frozen=True)
class OverlayConflictSplit:
    accepted: tuple[tuple[object, object | None], ...]
    preserved: tuple[tuple[object, object | None], ...]
    conflicts: dict[str, tuple[str, ...]]


def split_overlay_conflicts(
    repository_root: Path,
    items: tuple[tuple[object, object | None], ...],
) -> OverlayConflictSplit:
    """Keep regenerated objects unless an override's evidence changed."""

    root = Path(repository_root).resolve()
    overlays = load_active_overlays(root)
    try:
        from knowledge_compiler.incremental.invalidation import (
            load_generation_knowledge,
        )

        previous, packs = load_generation_knowledge(root)
    except Exception as error:
        # A missing prior generation is an ordinary first build. Every other
        # load failure must fail closed instead of bypassing an override.
        if not (root / ".knowledge/manifest.yaml").exists():
            previous, packs = {}, {}
        else:
            raise ValueError(
                f"cannot evaluate human override conflicts: {error}"
            ) from error

    accepted: list[tuple[object, object | None]] = []
    preserved: list[tuple[object, object | None]] = []
    conflicts: dict[str, tuple[str, ...]] = {}
    for candidate, pack in items:
        object_id = getattr(candidate, "id", None)
        overlay = overlays.get(object_id)
        old = previous.get(object_id)
        override_fields = tuple(
            section.field
            for section in (overlay.sections if overlay else ())
            if section.mode == "override"
        )
        changed = tuple(
            field
            for field in override_fields
            if old is not None
            and _field_evidence_identity(old, field)
            != _field_evidence_identity(candidate, field)
        )
        if changed:
            conflicts[str(object_id)] = changed
            preserved.append((old, packs.get(str(object_id))))
        else:
            accepted.append((candidate, pack))
    return OverlayConflictSplit(
        accepted=tuple(accepted),
        preserved=tuple(preserved),
        conflicts=dict(sorted(conflicts.items())),
    )


def _field_evidence_identity(canonical: object, field: str) -> str:
    validated = canonical.__class__.model_validate(
        canonical.model_dump(mode="json")
    )
    value = getattr(validated, field)
    claim_ids = sorted(_collect_claim_ids(value))
    claims = {claim.id: claim for claim in getattr(validated, "claims", ())}
    evidence = []
    for claim_id in claim_ids:
        claim = claims.get(claim_id)
        if claim is None:
            evidence.append((claim_id, "missing"))
            continue
        verification = getattr(claim, "verification", None)
        evidence.append(
            (
                claim_id,
                tuple(claim.evidence_ids),
                tuple(getattr(verification, "excerpt_hashes", ())),
            )
        )
    if not claim_ids:
        evidence.append(
            ("unclaimed-field", _json_value(value))
        )
    return json.dumps(evidence, sort_keys=True, separators=(",", ":"))


def _collect_claim_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, BaseModel):
        own = getattr(value, "claim_ids", None)
        if isinstance(own, tuple | list):
            found.update(item for item in own if isinstance(item, str))
        for field_name in value.__class__.model_fields:
            if field_name == "claim_ids":
                continue
            found.update(_collect_claim_ids(getattr(value, field_name)))
    elif isinstance(value, dict):
        for item in value.values():
            found.update(_collect_claim_ids(item))
    elif isinstance(value, tuple | list):
        for item in value:
            found.update(_collect_claim_ids(item))
    return found


def _json_value(value: Any) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


__all__ = ["OverlayConflictSplit", "split_overlay_conflicts"]
