from __future__ import annotations

from typing import Protocol

from knowledge_compiler.contracts.planning import KnowledgePlan, PlanRequest
from knowledge_compiler.contracts.semantic import (
    ExtractionRequest,
    ExtractionResult,
    VerificationRequest,
    VerificationResult,
)


class SemanticWorker(Protocol):
    def plan(self, request: PlanRequest) -> KnowledgePlan: ...

    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...

    def verify(self, request: VerificationRequest) -> VerificationResult: ...


__all__ = ["SemanticWorker"]
