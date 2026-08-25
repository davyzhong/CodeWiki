from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from knowledge_compiler.contracts import EvidencePack
from knowledge_compiler.contracts.knowledge import ExtractionResult
from knowledge_compiler.contracts.semantic import (
    ClaimVerificationResult,
    VerificationResult,
)
from knowledge_compiler.validation.module import (
    apply_verification_result,
    build_verification_request,
    validate_module_extraction,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fake_provider"
REPO = ROOT / "tests/fixtures/probe_repo"


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def extraction(payload: dict[str, object] | None = None) -> ExtractionResult:
    data = deepcopy(payload or load("module-extraction.json"))
    data["draft"]["scope"]["root"] = REPO
    return ExtractionResult.model_validate(data)


def pack(payload: dict[str, object] | None = None, root: Path = REPO) -> EvidencePack:
    data = deepcopy(payload or load("evidence-pack.json"))
    data["repository"]["root"] = root
    return EvidencePack.model_validate(data)


def issue_codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


@pytest.mark.parametrize("bad_path", ("/tmp/x.py", "../x.py", "C:\\x.py", "x.py\0"))
def test_source_integrity_rejects_unsafe_paths(tmp_path: Path, bad_path: str) -> None:
    data = load("evidence-pack.json")
    data["evidence"][0]["path"] = bad_path
    # Construct bypasses DTO validation so the integrity boundary is independently tested.
    evidence_pack = EvidencePack.model_construct(
        **{**data, "repository": pack(root=tmp_path).repository}
    )
    result = validate_module_extraction(extraction(), evidence_pack, tmp_path)
    assert "source.path.invalid" in issue_codes(result)


def test_source_integrity_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.py"
    outside.write_text("secret\n", encoding="utf-8")
    os.symlink(outside, tmp_path / "escape.py")
    data = load("evidence-pack.json")
    item = data["evidence"][0]
    item["path"] = "escape.py"
    evidence_pack = EvidencePack.model_construct(
        **{**data, "repository": pack(root=tmp_path).repository}
    )
    result = validate_module_extraction(extraction(), evidence_pack, tmp_path)
    assert "source.path.escape" in issue_codes(result)


def test_source_integrity_rejects_missing_invalid_utf8_and_range(tmp_path: Path) -> None:
    data = load("evidence-pack.json")
    evidence_pack = pack(data, tmp_path)
    assert "source.missing" in issue_codes(
        validate_module_extraction(extraction(), evidence_pack, tmp_path)
    )

    source = tmp_path / data["evidence"][0]["path"]
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\xff")
    assert "source.utf8" in issue_codes(
        validate_module_extraction(extraction(), evidence_pack, tmp_path)
    )

    source.write_bytes(b"only one line\n")
    assert "source.range" in issue_codes(
        validate_module_extraction(extraction(), evidence_pack, tmp_path)
    )


@pytest.mark.parametrize(
    ("field", "code"),
    (("content_hash", "source.content_hash"), ("excerpt_hash", "evidence.excerpt_hash"), ("id", "evidence.id")),
)
def test_source_integrity_rejects_hash_or_derived_id_mismatch(field: str, code: str) -> None:
    data = load("evidence-pack.json")
    data["evidence"][0][field] = "sha256:" + "f" * 64
    evidence_pack = EvidencePack.model_construct(
        **{**data, "repository": pack().repository}
    )
    result = validate_module_extraction(extraction(), evidence_pack, REPO)
    assert code in issue_codes(result)


def test_exact_source_bytes_preserve_crlf_and_trailing_newline(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_bytes(b"one\r\ntwo\r\nthree")
    data = load("evidence-pack.json")
    item = data["evidence"][0]
    item.update(path="source.py", start_line=1, end_line=2, symbol=None, excerpt="one\ntwo\n")
    item["content_hash"] = "sha256:" + hashlib.sha256(b"one\r\ntwo\r\n").hexdigest()
    item["excerpt_hash"] = "sha256:" + hashlib.sha256(b"one\ntwo\n").hexdigest()
    from knowledge_compiler.contracts import build_evidence_id
    repo = pack(root=tmp_path).repository
    item["id"] = build_evidence_id(repo.repository_id, repo.snapshot_id, "source.py", None, 1, 2, item["content_hash"])
    evidence_pack = EvidencePack.model_construct(**{**data, "repository": repo})
    result = validate_module_extraction(extraction(), evidence_pack, tmp_path)
    assert not ({"source.content_hash", "evidence.excerpt_hash", "evidence.id"} & issue_codes(result))


@pytest.mark.parametrize("field", ("summary", "responsibilities", "public_interfaces", "dependencies", "relations"))
def test_binding_rejects_unknown_claim_in_every_factual_field(field: str) -> None:
    result_data = load("module-extraction.json")
    draft = result_data["draft"]
    if field == "summary":
        draft[field]["claim_ids"] = ["module.shop.checkout.claim.unknown"]
    else:
        draft[field][0]["claim_ids"] = ["module.shop.checkout.claim.unknown"]
    result = validate_module_extraction(
        ExtractionResult.model_construct(**result_data), pack(), REPO
    )
    assert "claim.reference.unknown" in issue_codes(result)


def test_binding_rejects_unknown_evidence_missing_responsibility_and_empty_claim() -> None:
    data = load("module-extraction.json")
    data["draft"]["claims"][0]["evidence_ids"] = ["sha256:" + "f" * 64]
    data["draft"]["claims"][1]["evidence_ids"] = []
    data["draft"]["responsibilities"] = []
    result = validate_module_extraction(
        ExtractionResult.model_construct(**data), pack(), REPO
    )
    assert {"claim.evidence.unknown", "claim.evidence.missing", "responsibility.required"} <= issue_codes(result)
    assert result.issues == tuple(sorted(result.issues, key=lambda i: (i.code, i.location)))


def test_binding_rejects_snapshot_mismatch_and_never_repairs_input() -> None:
    value = extraction()
    object.__setattr__(value, "snapshot_id", "sha256:" + "f" * 64)
    before = value.model_dump()
    result = validate_module_extraction(value, pack(), REPO)
    assert "identity.snapshot" in issue_codes(result)
    assert value.model_dump() == before


def test_valid_fixture_builds_canonical_digest_and_only_claim_backed_payload() -> None:
    value = extraction()
    evidence_pack = pack()
    checked = validate_module_extraction(value, evidence_pack, REPO)
    assert checked.is_valid
    request = build_verification_request(value, evidence_pack, REPO)
    assert [claim.claim_id for claim in request.claims] == sorted(c.id for c in value.draft.claims)
    assert all(claim.statement for claim in request.claims)
    assert all(entry.excerpt and entry.excerpt_hash for claim in request.claims for entry in claim.evidence)
    canonical = [
        {
            "claim_id": claim.claim_id,
            "statement": claim.statement,
            "evidence": [[entry.evidence_id, entry.excerpt_hash] for entry in claim.evidence],
        }
        for claim in request.claims
    ]
    expected = "sha256:" + hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert request.verification_request_digest == expected


def valid_semantic_objects():
    value = extraction()
    evidence_pack = pack()
    request = build_verification_request(value, evidence_pack, REPO)
    raw = load("module-verification.json")
    raw["verification_request_digest"] = request.verification_request_digest
    for verification in raw["verifications"]:
        verification["verification_request_digest"] = request.verification_request_digest
    return value, evidence_pack, request, VerificationResult.model_validate(raw)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("run_id", "other-run"), ("attempt", 2), ("target_id", "module.shop.other"),
        ("snapshot_id", "sha256:" + "f" * 64), ("operation", "extract"),
        ("idempotency_key", "other-key"), ("verification_request_digest", "sha256:" + "f" * 64),
    ),
)
def test_apply_rejects_uncorrelated_result_envelope(field: str, replacement: object) -> None:
    value, evidence_pack, request, result = valid_semantic_objects()
    changed = result.model_copy(update={field: replacement})
    checked = apply_verification_result(value, evidence_pack, request, changed, REPO)
    assert checked.module is None
    assert any(issue.code.startswith("verification.correlation") for issue in checked.issues)


@pytest.mark.parametrize("status", ("partial", "unsupported", "conflicted"))
def test_apply_rejects_every_non_supported_status(status: str) -> None:
    value, evidence_pack, request, result = valid_semantic_objects()
    first = result.verifications[0].model_copy(update={"status": status})
    changed = result.model_copy(update={"verifications": (first, *result.verifications[1:])})
    checked = apply_verification_result(value, evidence_pack, request, changed, REPO)
    assert "verification.status" in issue_codes(checked)


@pytest.mark.parametrize("mutation", ("missing", "evidence", "excerpt", "text", "claim_digest"))
def test_apply_rejects_missing_or_changed_claim_bindings(mutation: str) -> None:
    value, evidence_pack, request, result = valid_semantic_objects()
    verifications = list(result.verifications)
    if mutation == "missing":
        verifications.pop()
    else:
        first = verifications[0]
        if mutation == "evidence":
            first = first.model_copy(update={"evidence_ids": ("sha256:" + "f" * 64,)})
        elif mutation == "excerpt":
            first = first.model_copy(update={"excerpt_hashes": ("sha256:" + "f" * 64,)})
        elif mutation == "text":
            first = first.model_copy(update={"excerpts": ("changed",)})
        else:
            first = first.model_copy(update={"verification_request_digest": "sha256:" + "f" * 64})
        verifications[0] = first
    changed = result.model_copy(update={"verifications": tuple(verifications)})
    checked = apply_verification_result(value, evidence_pack, request, changed, REPO)
    assert checked.module is None
    assert any(issue.code.startswith("verification.") for issue in checked.issues)


def test_apply_constructs_new_canonical_module_and_copies_provenance() -> None:
    value, evidence_pack, request, result = valid_semantic_objects()
    checked = apply_verification_result(value, evidence_pack, request, result, REPO)
    assert checked.is_valid and checked.module is not None
    assert checked.module.provenance == value.provenance
    assert checked.module.confidence == value.draft.confidence
    assert checked.module is not value.draft
    assert all(claim.verification.status == "supported" for claim in checked.module.claims)
