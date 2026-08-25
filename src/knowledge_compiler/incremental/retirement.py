from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RetirementCandidate(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    object_id: str
    evidence_paths: tuple[str, ...]
    former_symbols: tuple[str, ...]
    inbound_relations: tuple[str, ...]


class RetirementCheck(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    candidate: RetirementCandidate
    source_absent: bool
    search_complete: bool
    search_found_current: bool
    inbound_relations_verified: bool


def evaluate_retirement(check: RetirementCheck) -> bool:
    """Retire only when all four deterministic proofs hold.

    Model output, vector search, planner omission, and insufficient
    evidence never authorize deletion — only this proof set does.
    """

    return (
        check.source_absent
        and check.search_complete
        and not check.search_found_current
        and check.inbound_relations_verified
    )


__all__ = [
    "RetirementCandidate",
    "RetirementCheck",
    "evaluate_retirement",
]
