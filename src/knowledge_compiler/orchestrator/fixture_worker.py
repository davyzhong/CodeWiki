from __future__ import annotations

import json
from pathlib import Path


def _fixtures() -> Path:
    candidate = (Path(__file__).resolve().parents[3] / "tests/fixtures/fake_provider").resolve()
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError("fixture world unavailable in this checkout")


class FixtureWorker:
    """Deterministic semantic worker over the fixture drafts."""

    def extract(self, request):
        from knowledge_compiler.contracts.knowledge import ExtractionResult

        payload = json.loads(
            (_fixtures() / "module-extraction.json").read_text(encoding="utf-8")
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

        payload = json.loads(
            (_fixtures() / "module-verification.json").read_text(encoding="utf-8")
        )
        for field in (
            "contract_version", "run_id", "target_id", "operation",
            "attempt", "snapshot_id", "idempotency_key",
        ):
            payload[field] = getattr(request, field)
        return VerificationResult.model_validate(payload)


__all__ = ["FixtureWorker"]
