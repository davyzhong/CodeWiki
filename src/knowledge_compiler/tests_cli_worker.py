from __future__ import annotations

import json
from pathlib import Path


class StubWorker:
    """Deterministic CLI worker over the fixture drafts."""

    def extract(self, request):
        from knowledge_compiler.contracts.knowledge import ExtractionResult

        fixtures = (
            Path(__file__).resolve().parents[1] / "fixtures/fake_provider"
        )
        payload = json.loads(
            (fixtures / "module-extraction.json").read_text(encoding="utf-8")
        )
        payload["draft"]["scope"] = {
            "repository": request.evidence_pack.repository.repository_id,
            "root": str(request.evidence_pack.repository.root),
            "branch": request.evidence_pack.repository.branch,
            "commit": request.evidence_pack.repository.commit,
            "dirty": request.evidence_pack.repository.dirty,
            "working_tree_hash": request.evidence_pack.repository.working_tree_hash,
        }
        for field in (
            "contract_version", "run_id", "target_id", "operation",
            "attempt", "snapshot_id", "idempotency_key",
        ):
            payload[field] = getattr(request, field)
        return ExtractionResult.model_validate(payload)

    def verify(self, request):
        from knowledge_compiler.contracts.semantic import VerificationResult

        fixtures = (
            Path(__file__).resolve().parents[1] / "fixtures/fake_provider"
        )
        payload = json.loads(
            (fixtures / "module-verification.json").read_text(encoding="utf-8")
        )
        for field in (
            "contract_version", "run_id", "target_id", "operation",
            "attempt", "snapshot_id", "idempotency_key",
        ):
            payload[field] = getattr(request, field)
        return VerificationResult.model_validate(payload)


__all__ = ["StubWorker"]
