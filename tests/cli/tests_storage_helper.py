from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/fake_provider"
REPOSITORY_ROOT = (ROOT / "fixtures/probe_repo").resolve()


def build_published_generation(output_root: Path) -> None:
    """Publish one module generation through the fake provider pipeline."""

    from knowledge_compiler.contracts import EvidencePack
    from knowledge_compiler.contracts.knowledge import ExtractionResult
    from knowledge_compiler.contracts.semantic import (
        ExtractionRequest,
        VerificationResult,
    )
    from knowledge_compiler.storage import GenerationPublisher
    from knowledge_compiler.validation.module import (
        apply_verification_result,
        build_verification_request,
    )

    extraction_data = json.loads(
        (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
    )
    extraction_data["draft"]["scope"]["root"] = str(REPOSITORY_ROOT)
    extraction = ExtractionResult.model_validate(extraction_data)
    pack_data = json.loads(
        (FIXTURES / "evidence-pack.json").read_text(encoding="utf-8")
    )
    pack_data["repository"]["root"] = str(REPOSITORY_ROOT)
    pack = EvidencePack.model_validate(pack_data)
    request = ExtractionRequest.model_validate(
        {
            "contract_version": extraction.contract_version,
            "run_id": extraction.run_id,
            "target_id": extraction.target_id,
            "operation": extraction.operation,
            "attempt": extraction.attempt,
            "snapshot_id": extraction.snapshot_id,
            "idempotency_key": extraction.idempotency_key,
            "evidence_pack": pack,
        }
    )
    verification_request = build_verification_request(
        request, extraction, REPOSITORY_ROOT
    )
    verified = apply_verification_result(
        request,
        extraction,
        verification_request,
        VerificationResult.model_validate(
            json.loads(
                (FIXTURES / "module-verification.json").read_text(encoding="utf-8")
            )
        ),
        REPOSITORY_ROOT,
    )
    assert verified.is_valid and verified.module is not None
    GenerationPublisher(output_root).publish(
        "gen-validate-001", verified.module, pack
    )


__all__ = ["build_published_generation"]
