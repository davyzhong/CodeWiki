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
    changed: Literal[False] = False


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
