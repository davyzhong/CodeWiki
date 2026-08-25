from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_compiler.contracts.repository import (
    EvidenceBudget,
    PlanTarget,
    RepositorySnapshot,
    build_snapshot_id,
)
from knowledge_compiler.contracts.evidence import EvidencePack
from knowledge_compiler.contracts.knowledge import ExtractionResult
from knowledge_compiler.contracts.semantic import (
    ExtractionRequest,
    VerificationRequest,
    VerificationResult,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fake_provider"
REPOSITORY_ROOT = (ROOT / "tests/fixtures/probe_repo").resolve()


def make_pack() -> EvidencePack:
    import shutil
    import tempfile

    from knowledge_compiler.providers.fake import FakeEvidenceProvider

    tmp = Path(tempfile.mkdtemp())
    copied = tmp / "repo"
    shutil.copytree(REPOSITORY_ROOT, copied)
    provider = FakeEvidenceProvider(fixture_dir=FIXTURES, repository_root=copied)
    snapshot = provider.bound_repository()
    target = PlanTarget(
        id="module.shop.checkout",
        topic="CheckoutService",
        evidence_seeds=("CheckoutService", "Inventory.reserve"),
    )
    pack = provider.build_pack(
        snapshot,
        target,
        EvidenceBudget(max_items=4, max_characters=4000, max_tokens=512),
    )
    # The temporary copy stays alive for the test's duration: source
    # validation reads the bound root on disk.
    return pack


def make_request() -> ExtractionRequest:
    pack = make_pack()
    data = json.loads(
        (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
    )
    data["draft"]["scope"]["root"] = str(pack.repository.root)
    extraction = ExtractionResult.model_validate(data)
    return ExtractionRequest.model_validate(
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


def pack_scope(request: ExtractionRequest) -> dict:
    repo = request.evidence_pack.repository
    return {
        "repository": repo.repository_id,
        "root": str(repo.root),
        "branch": repo.branch,
        "commit": repo.commit,
        "dirty": repo.dirty,
        "working_tree_hash": repo.working_tree_hash,
    }


class FakeTransport:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, *, system: str, user: str, model: str) -> str:
        self.prompts.append(system + "\n" + user)
        if not self._replies:
            raise RuntimeError("transport exhausted")
        return self._replies.pop(0)


def make_worker(transport):
    from knowledge_compiler.workers.litellm_worker import LiteLLMWorker

    return LiteLLMWorker(
        transport=transport,
        extraction_model="test-extraction-model",
        verification_model="test-verification-model",
    )


def test_extract_success_round_trips_contract() -> None:
    request = make_request()
    reply = json.loads(
        (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
    )
    reply["draft"]["scope"] = pack_scope(request)
    transport = FakeTransport([json.dumps(reply)])
    worker = make_worker(transport)
    result = worker.extract(request)
    assert isinstance(result, ExtractionResult)
    assert result.target_id == request.target_id
    assert result.provenance.model == "test-extraction-model"
    assert result.provenance.generated_at.tzinfo is not None


def test_extract_prompt_contains_only_pack_evidence() -> None:
    request = make_request()
    reply = json.loads(
        (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
    )
    reply["draft"]["scope"] = pack_scope(request)
    transport = FakeTransport([json.dumps(reply)])
    make_worker(transport).extract(request)
    prompt = transport.prompts[0]
    for item in request.evidence_pack.evidence:
        assert item.path in prompt
    assert "/Users/" not in prompt.replace(str(request.evidence_pack.repository.root), "")


def test_extract_prompt_is_typed_and_not_module_specific() -> None:
    from knowledge_compiler.workers.litellm_worker import _extraction_prompt

    request = make_request()
    target = PlanTarget(
        id="architecture.shop.overview",
        type="architecture",
        topic=request.evidence_pack.target.topic,
        evidence_seeds=request.evidence_pack.target.evidence_seeds,
    )
    pack = request.evidence_pack.model_copy(update={"target": target})
    typed_request = request.model_copy(
        update={"target_id": target.id, "evidence_pack": pack}
    )

    system, user = _extraction_prompt(typed_request)

    assert "one module" not in system.lower()
    assert "architecture" in system.lower()
    assert "type=architecture" in user


def test_extract_repairs_malformed_json_twice_then_fails_typed() -> None:
    request = make_request()
    transport = FakeTransport(["{not json", "{still not json", "{nope"])
    worker = make_worker(transport)
    with pytest.raises(Exception, match="malformed"):
        worker.extract(request)
    assert len(transport.prompts) == 3  # initial + two repairs


def test_extract_schema_mismatch_fails_typed() -> None:
    request = make_request()
    transport = FakeTransport([json.dumps({"nonsense": True})])
    worker = make_worker(transport)
    with pytest.raises(Exception, match="schema|contract"):
        worker.extract(request)


def test_extract_provider_failure_and_timeout_fail_typed() -> None:
    request = make_request()

    class Exploding:
        def __init__(self, error: Exception) -> None:
            self._error = error

        def __call__(self, **_kwargs: object) -> str:
            raise self._error

    from knowledge_compiler.workers.litellm_worker import WorkerTransportError

    with pytest.raises(WorkerTransportError):
        make_worker(Exploding(TimeoutError("timed out"))).extract(request)
    with pytest.raises(WorkerTransportError):
        make_worker(Exploding(RuntimeError("provider down"))).extract(request)


def test_verify_success_and_separate_prompt() -> None:
    from knowledge_compiler.validation.module import build_verification_request

    request = make_request()
    extraction_payload = json.loads(
        (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
    )
    extraction_payload["draft"]["scope"]["root"] = str(
        request.evidence_pack.repository.root
    )
    extraction = ExtractionResult.model_validate(extraction_payload)
    verification_request = build_verification_request(
        request, extraction, request.evidence_pack.repository.root
    )
    assert isinstance(verification_request, VerificationRequest)
    reply = json.loads(
        (FIXTURES / "module-verification.json").read_text(encoding="utf-8")
    )
    transport = FakeTransport([json.dumps(reply)])
    worker = make_worker(transport)
    result = worker.verify(verification_request)
    assert isinstance(result, VerificationResult)
    assert result.idempotency_key == verification_request.idempotency_key
    assert "verif" in transport.prompts[0].lower()


def test_prompts_never_contain_secrets() -> None:
    import os

    request = make_request()
    reply = json.loads(
        (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
    )
    reply["draft"]["scope"] = pack_scope(request)
    secret = "sk-test-secret-value-1234567890"
    os.environ["KNOWLEDGE_TEST_KEY"] = secret
    try:
        transport = FakeTransport([json.dumps(reply)])
        make_worker(transport).extract(request)
        assert secret not in transport.prompts[0]
    finally:
        del os.environ["KNOWLEDGE_TEST_KEY"]
