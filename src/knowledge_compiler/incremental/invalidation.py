from __future__ import annotations

from dataclasses import dataclass

from knowledge_compiler.contracts.knowledge import ModuleKnowledge
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
    canonical: ModuleKnowledge, *, reason: str, evidence_path: str
) -> ModuleKnowledge:
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


__all__ = [
    "InvalidationResult",
    "compute_affected",
    "mark_stale",
    "merge_hints",
]
