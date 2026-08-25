from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge_compiler.contracts.repository import (
    NonBlankString,
    PlanTarget,
)


class PlanRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    contract_version: Literal["0.1"] = "0.1"
    run_id: NonBlankString
    repository_id: NonBlankString
    snapshot_id: NonBlankString
    operation: Literal["plan"] = "plan"
    attempt: int = Field(strict=True, gt=0)
    idempotency_key: NonBlankString


class PlanTargetSpec(BaseModel):
    """A planned target with scheduling metadata the planner may own."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    target: PlanTarget
    priority: int = Field(strict=True, ge=1, le=9)
    required: bool = True


class KnowledgePlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    contract_version: Literal["0.1"] = "0.1"
    run_id: NonBlankString
    repository_id: NonBlankString
    snapshot_id: NonBlankString
    operation: Literal["plan"] = "plan"
    attempt: int = Field(strict=True, gt=0)
    idempotency_key: NonBlankString
    targets: tuple[PlanTargetSpec, ...] = ()

    @model_validator(mode="after")
    def order_targets(self) -> "KnowledgePlan":
        if len({spec.target.id for spec in self.targets}) != len(self.targets):
            raise ValueError("duplicate plan target ids are not allowed")
        return self


__all__ = [
    "KnowledgePlan",
    "PlanRequest",
    "PlanTargetSpec",
]
