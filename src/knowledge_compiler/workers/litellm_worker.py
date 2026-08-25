from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from knowledge_compiler.contracts.planning import PlanRequest
from knowledge_compiler.contracts.semantic import (
    ExtractionRequest,
    ExtractionResult,
    VerificationRequest,
    VerificationResult,
)


MAX_REPAIR_ATTEMPTS = 2


class WorkerTransportError(RuntimeError):
    """Raised when the model transport fails or times out."""


class WorkerOutputError(ValueError):
    """Raised when model output stays malformed or schema-invalid."""


Transport = Callable[..., str]


def _extraction_prompt(request: ExtractionRequest) -> tuple[str, str]:
    pack = request.evidence_pack
    evidence_lines = []
    for item in pack.evidence:
        evidence_lines.append(
            f"- {item.path}:{item.start_line}-{item.end_line} "
            f"symbol={item.symbol}\n```\n{item.excerpt}\n```"
        )
    facts = "\n".join(
        f"- {fact.source} {fact.predicate} {fact.target}"
        for fact in pack.graph_facts
    )
    system = (
        "You extract one module knowledge draft from bounded evidence. "
        "Return ONLY JSON matching the ExtractionResult contract. Never "
        "invent evidence; if the evidence is insufficient, return an error "
        "object with reason insufficient_evidence."
    )
    user = (
        f"Repository {pack.repository.repository_id} commit {pack.repository.commit}\n"
        f"Target {pack.target.id} topic {pack.target.topic}\n\n"
        "Evidence (redacted excerpts only):\n"
        + "\n".join(evidence_lines)
        + "\n\nGraph facts:\n"
        + facts
        + "\n\nEnvelope to echo verbatim:\n"
        + json.dumps(
            {
                "contract_version": request.contract_version,
                "run_id": request.run_id,
                "target_id": request.target_id,
                "operation": request.operation,
                "attempt": request.attempt,
                "snapshot_id": request.snapshot_id,
                "idempotency_key": request.idempotency_key,
            }
        )
    )
    return system, user


def _verification_prompt(request: VerificationRequest) -> tuple[str, str]:
    claim_lines = []
    for claim in request.claims:
        evidence = "\n".join(
            f"- {entry.evidence_id}\n```\n{entry.excerpt}\n```"
            for entry in claim.evidence
        )
        claim_lines.append(
            f"Claim {claim.claim_id}: {claim.statement}\n{evidence}"
        )
    system = (
        "You are an independent verifier. For each claim, decide supported, "
        "partial, unsupported, or conflicted using ONLY the cited redacted "
        "evidence. Return ONLY JSON matching the VerificationResult contract."
    )
    user = (
        "Claims to verify:\n"
        + "\n\n".join(claim_lines)
        + "\n\nEnvelope to echo verbatim:\n"
        + json.dumps(
            {
                "contract_version": request.contract_version,
                "run_id": request.run_id,
                "target_id": request.target_id,
                "operation": request.operation,
                "attempt": request.attempt,
                "snapshot_id": request.snapshot_id,
                "idempotency_key": request.idempotency_key,
                "verification_request_digest": request.verification_request_digest,
            }
        )
    )
    return system, user


class LiteLLMWorker:
    """Semantic worker over an injectable LiteLLM-style transport."""

    def __init__(
        self,
        *,
        transport: Transport,
        extraction_model: str,
        verification_model: str | None = None,
    ) -> None:
        self._transport = transport
        self._extraction_model = extraction_model
        self._verification_model = verification_model or extraction_model

    def plan(self, request: PlanRequest) -> object:
        from knowledge_compiler.planning.module import plan_one_module

        raise NotImplementedError(
            "model-backed planning arrives with the orchestrator; use the "
            "deterministic planner directly in M2"
        )

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        system, user = _extraction_prompt(request)
        payload = self._complete(system, user, self._extraction_model)
        binding = {
            "draft": payload.get("draft") if isinstance(payload, dict) else None,
            "provenance": self._provenance("extraction"),
        }
        envelope = request.model_dump(
            include={
                "contract_version", "run_id", "target_id", "operation",
                "attempt", "snapshot_id", "idempotency_key",
            }
        )
        return self._validate(ExtractionResult, {**envelope, **binding})

    def verify(self, request: VerificationRequest) -> VerificationResult:
        system, user = _verification_prompt(request)
        payload = self._complete(system, user, self._verification_model)
        envelope = request.model_dump(
            include={
                "contract_version", "run_id", "target_id", "operation",
                "attempt", "snapshot_id", "idempotency_key",
                "verification_request_digest",
            }
        )
        return self._validate(
            VerificationResult,
            {**envelope, "verifications": payload.get("verifications")},
        )

    def _complete(self, system: str, user: str, model: str) -> dict:
        attempts = 0
        last_error: Exception | None = None
        while attempts <= MAX_REPAIR_ATTEMPTS:
            attempts += 1
            try:
                raw = self._transport(system=system, user=user, model=model)
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    return payload
                last_error = WorkerOutputError("model output is not a JSON object")
            except WorkerTransportError:
                raise
            except (TimeoutError, RuntimeError, OSError) as error:
                raise WorkerTransportError(f"model transport failed: {error}") from error
            except ValueError as error:
                last_error = WorkerOutputError(f"malformed model JSON: {error}")
        raise last_error or WorkerOutputError("malformed model output")

    @staticmethod
    def _validate(model_type, payload):
        try:
            return model_type.model_validate(payload)
        except ValidationError as error:
            raise WorkerOutputError(f"model output failed the contract: {error}") from error

    def _provenance(self, operation: str) -> dict:
        return {
            "execution_mode": "llm",
            "model": (
                self._extraction_model
                if operation == "extraction"
                else self._verification_model
            ),
            "prompt_version": "module-extraction-v1"
            if operation == "extraction"
            else "module-verification-v1",
            "schema_version": "0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


__all__ = [
    "LiteLLMWorker",
    "WorkerOutputError",
    "WorkerTransportError",
]
