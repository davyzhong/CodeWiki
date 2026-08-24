from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonBlankString = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_snapshot_id(
    repository_id: str,
    commit: str,
    dirty: bool,
    working_tree_hash: str | None,
) -> str:
    return _canonical_sha256(
        [repository_id, commit, dirty, working_tree_hash or ""]
    )


class RepositorySnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    repository_id: NonBlankString
    snapshot_id: str
    root: Path
    branch: NonBlankString | None
    commit: NonBlankString
    dirty: bool
    working_tree_hash: str | None = None
    eligible_files: tuple[NonBlankString, ...] = ()

    @model_validator(mode="after")
    def validate_identity(self) -> RepositorySnapshot:
        if not self.root.is_absolute():
            raise ValueError("repository root must be absolute")
        expected = build_snapshot_id(
            self.repository_id,
            self.commit,
            self.dirty,
            self.working_tree_hash,
        )
        if self.snapshot_id != expected:
            raise ValueError(f"snapshot_id does not match derived identity: {expected}")
        return self


class PlanTarget(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    id: NonBlankString
    type: Literal["module"] = "module"
    topic: NonBlankString
    evidence_seeds: tuple[NonBlankString, ...] = ()


class EvidenceBudget(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    max_items: int = Field(strict=True, gt=0)
    max_characters: int = Field(strict=True, gt=0)
    max_tokens: int = Field(strict=True, gt=0)
