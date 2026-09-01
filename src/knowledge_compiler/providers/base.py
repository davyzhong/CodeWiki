from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from knowledge_compiler.contracts import (
    EvidenceBudget,
    EvidenceItem,
    EvidencePack,
    PlanTarget,
    RepositorySnapshot,
    RepositorySurvey,
)
from knowledge_compiler.contracts.repository import NonBlankString


class IndexStatus(BaseModel):
    """Project-owned result of making an evidence index ready for a snapshot."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        validate_default=True,
    )

    repository_id: NonBlankString
    snapshot_id: NonBlankString
    state: Literal["ready"] = "ready"
    changed: bool = False


class AffectedHints(BaseModel):
    """Provider-side affected-symbol hints enriching a local ChangeSet.

    Hints are advisory: safe invalidation remains locally derived and a
    hint failure never blocks or replaces it.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        validate_default=True,
    )

    repository_id: NonBlankString
    snapshot_id: NonBlankString
    affected_files: tuple[NonBlankString, ...] = ()
    affected_node_ids: tuple[NonBlankString, ...] = ()
    affected_tests: tuple[NonBlankString, ...] = ()
    complete: bool = True


class ProviderHintError(RuntimeError):
    """A provider incremental surface failed; callers degrade safely."""


@runtime_checkable
class EvidenceProvider(Protocol):
    def inspect(self, repo: RepositorySnapshot) -> RepositorySurvey: ...

    def ensure_index(self, repo: RepositorySnapshot) -> IndexStatus: ...

    def build_pack(
        self,
        repo: RepositorySnapshot,
        target: PlanTarget,
        budget: EvidenceBudget,
    ) -> EvidencePack: ...

    def get_evidence(
        self,
        repo: RepositorySnapshot,
        evidence_id: str,
    ) -> EvidenceItem: ...


@runtime_checkable
class IncrementalEvidenceProvider(EvidenceProvider, Protocol):
    """Provider surface used only after Knowledge Compiler computed its
    own local ChangeSet."""

    def sync_incremental(
        self,
        repo: RepositorySnapshot,
        changes: object,
    ) -> IndexStatus: ...

    def affected(
        self,
        repo: RepositorySnapshot,
        changes: object,
    ) -> AffectedHints: ...
