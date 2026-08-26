from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from knowledge_compiler.repository.inventory import FileRecord


class Change(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    path: str
    old_hash: str | None = None
    new_hash: str | None = None


class ChangeSet(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    added: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    renamed: tuple[tuple[str, str], ...] = ()

    @model_validator(mode="after")
    def sorted_and_disjoint(self) -> "ChangeSet":
        self.__dict__["added"] = tuple(sorted(set(self.added)))
        self.__dict__["modified"] = tuple(sorted(set(self.modified)))
        self.__dict__["deleted"] = tuple(sorted(set(self.deleted)))
        overlap = set(self.added) & set(self.modified)
        overlap |= set(self.added) & set(self.deleted)
        overlap |= set(self.modified) & set(self.deleted)
        if overlap:
            raise ValueError(f"overlapping change categories: {sorted(overlap)}")
        return self

    def is_empty(self) -> bool:
        return not (self.added or self.modified or self.deleted or self.renamed)


def compute_changes(
    baseline: tuple[FileRecord, ...], current: tuple[FileRecord, ...]
) -> ChangeSet:
    """Compare two eligible-file inventories into a deterministic ChangeSet.

    Change detection is baseline-authoritative: it never depends on the
    provider cache or Git history depth. A rename is normalized to
    delete+add unless both Git blob identity and content hash prove
    identity, which lands it in the renamed category.
    """

    baseline_by_path = {record.path: record for record in baseline}
    current_by_path = {record.path: record for record in current}

    added: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []

    for path, record in current_by_path.items():
        prior = baseline_by_path.get(path)
        if prior is None:
            added.append(path)
        elif prior.content_hash != record.content_hash:
            modified.append(path)

    for path in baseline_by_path:
        if path not in current_by_path:
            deleted.append(path)

    # Rename detection: a deleted file with the exact content hash of an
    # added file is a proven rename (same bytes), recorded as such.
    renamed: list[tuple[str, str]] = []
    added_identities: dict[tuple[str, str], str] = {}
    for path in added:
        record = current_by_path[path]
        if record.blob_id is not None:
            added_identities[(record.blob_id, record.content_hash)] = path
    remaining_deleted: list[str] = []
    for path in deleted:
        prior = baseline_by_path[path]
        identity = (
            (prior.blob_id, prior.content_hash)
            if prior.blob_id is not None
            else None
        )
        match = added_identities.get(identity) if identity is not None else None
        if match is not None:
            renamed.append((path, match))
            added.remove(match)
            del added_identities[identity]
        else:
            remaining_deleted.append(path)

    return ChangeSet(
        added=tuple(added),
        modified=tuple(modified),
        deleted=tuple(remaining_deleted),
        renamed=tuple(sorted(renamed)),
    )


__all__ = ["Change", "ChangeSet", "compute_changes"]
