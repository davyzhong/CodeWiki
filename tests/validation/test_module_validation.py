from __future__ import annotations

import hashlib
import json
import os
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_compiler.contracts import EvidencePack
from knowledge_compiler.contracts.knowledge import ExtractionResult
from knowledge_compiler.contracts.semantic import (
    ClaimVerificationResult,
    ExtractionRequest,
    VerificationRequest,
    VerificationResult,
)
from knowledge_compiler.validation.module import (
    ModuleValidationError,
    apply_verification_result,
    build_verification_request as build_verification_request_boundary,
    validate_module_extraction as validate_module_extraction_boundary,
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


def extraction_request(
    value: ExtractionResult | None = None,
    evidence_pack: EvidencePack | None = None,
) -> ExtractionRequest:
    value = value or extraction()
    return ExtractionRequest.model_validate(
        {
            **{name: getattr(value, name) for name in ENVELOPE_FIELDS},
            "evidence_pack": evidence_pack or pack(),
        }
    )


def validate_module_extraction(
    value: ExtractionResult, evidence_pack: EvidencePack, repository_root: Path
):
    return validate_module_extraction_boundary(
        extraction_request(value, evidence_pack), value, repository_root
    )


def build_verification_request(
    value: ExtractionResult, evidence_pack: EvidencePack, repository_root: Path
) -> VerificationRequest:
    return build_verification_request_boundary(
        extraction_request(value, evidence_pack), value, repository_root
    )


def apply_verification(
    value: ExtractionResult,
    evidence_pack: EvidencePack,
    request: VerificationRequest,
    result: VerificationResult,
    repository_root: Path,
):
    return apply_verification_result(
        extraction_request(value, evidence_pack),
        value,
        request,
        result,
        repository_root,
    )


def issue_codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def bound_fixture(root: Path) -> tuple[ExtractionRequest, ExtractionResult]:
    result_data = load("module-extraction.json")
    result_data["draft"]["scope"]["root"] = root
    value = ExtractionResult.model_validate(result_data)
    return extraction_request(value, pack(root=root)), value


ENVELOPE_FIELDS = (
    "contract_version",
    "run_id",
    "target_id",
    "operation",
    "attempt",
    "snapshot_id",
    "idempotency_key",
)


@pytest.mark.parametrize("field", ENVELOPE_FIELDS)
def test_extraction_result_requires_every_envelope_field(field: str) -> None:
    data = load("module-extraction.json")
    data["draft"]["scope"]["root"] = REPO
    data.pop(field)

    with pytest.raises(ValidationError, match=field):
        ExtractionResult.model_validate(data)


@pytest.mark.parametrize(
    "model_name",
    ("extraction-request", "verification-request", "verification-result"),
)
@pytest.mark.parametrize("field", ENVELOPE_FIELDS)
def test_semantic_contracts_require_every_envelope_field(
    model_name: str, field: str
) -> None:
    value = extraction()
    evidence_pack = pack()
    request = build_verification_request(value, evidence_pack, REPO)
    result_data = load("module-verification.json")
    if model_name == "extraction-request":
        model = ExtractionRequest
        payload = {
            **{name: getattr(value, name) for name in ENVELOPE_FIELDS},
            "evidence_pack": evidence_pack,
        }
    elif model_name == "verification-request":
        model = VerificationRequest
        payload = request.model_dump()
    else:
        model = VerificationResult
        payload = result_data
    payload.pop(field)

    with pytest.raises(ValidationError, match=field):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("contract_version", "0.2"),
        ("run_id", "other-run"),
        ("target_id", "module.shop.other"),
        ("operation", "verify"),
        ("attempt", 2),
        ("snapshot_id", "sha256:" + "f" * 64),
        ("idempotency_key", "other-key"),
    ),
)
def test_extraction_request_and_result_require_complete_envelope_correlation(
    field: str, replacement: object
) -> None:
    value = extraction()
    request = extraction_request(value, pack())
    changed = value.model_copy(update={field: replacement})

    checked = validate_module_extraction_boundary(request, changed, REPO)

    assert checked.module is None
    expected_code = (
        "contract.invalid"
        if field in {"contract_version", "operation"}
        else "extraction.correlation"
    )
    assert expected_code in issue_codes(checked)


def test_validation_revalidates_copied_extraction_claim_and_provenance() -> None:
    value = extraction()
    bad_claim = value.draft.claims[0].model_copy(
        update={"statement": "", "evidence_ids": ()}
    )
    bad_draft = value.draft.model_copy(
        update={"claims": (bad_claim, *value.draft.claims[1:])}
    )
    bad_provenance = value.provenance.model_copy(
        update={"generated_at": datetime(2026, 8, 25, 9, 30)}
    )
    changed = value.model_copy(
        update={"draft": bad_draft, "provenance": bad_provenance}
    )

    checked = validate_module_extraction_boundary(
        extraction_request(value, pack()), changed, REPO
    )

    assert checked.module is None
    assert "contract.invalid" in issue_codes(checked)
    assert any("statement" in issue.location for issue in checked.issues)
    assert any("evidence_ids" in issue.location for issue in checked.issues)
    assert any("generated_at" in issue.location for issue in checked.issues)


def test_validation_revalidates_nested_copied_evidence_pack() -> None:
    value = extraction()
    evidence_pack = pack()
    bad_item = evidence_pack.evidence[0].model_copy(
        update={"excerpt_hash": "malformed"}
    )
    bad_pack = evidence_pack.model_copy(
        update={"evidence": (bad_item, *evidence_pack.evidence[1:])}
    )
    bad_request = extraction_request(value, evidence_pack).model_copy(
        update={"evidence_pack": bad_pack}
    )

    checked = validate_module_extraction_boundary(bad_request, value, REPO)

    assert checked.module is None
    assert "contract.invalid" in issue_codes(checked)
    assert any("evidence_pack.evidence.0.excerpt_hash" in issue.location for issue in checked.issues)


def test_build_raises_typed_validation_error_with_stable_issues() -> None:
    value = extraction()
    bad_claim = value.draft.claims[0].model_copy(update={"statement": ""})
    changed = value.model_copy(
        update={
            "draft": value.draft.model_copy(
                update={"claims": (bad_claim, *value.draft.claims[1:])}
            )
        }
    )

    with pytest.raises(ModuleValidationError) as caught:
        build_verification_request_boundary(
            extraction_request(value, pack()), changed, REPO
        )

    assert caught.value.issues
    assert caught.value.issues == tuple(
        sorted(
            caught.value.issues,
            key=lambda issue: (issue.code, issue.location, issue.message),
        )
    )


@pytest.mark.parametrize("bad_path", ("/tmp/x.py", "../x.py", "C:\\x.py", "x.py\0"))
def test_source_integrity_rejects_unsafe_paths(tmp_path: Path, bad_path: str) -> None:
    data = load("evidence-pack.json")
    data["evidence"][0]["path"] = bad_path
    # Construct bypasses DTO validation so the integrity boundary is independently tested.
    evidence_pack = EvidencePack.model_construct(
        **{**data, "repository": pack(root=tmp_path).repository}
    )
    value = extraction()
    valid_request = extraction_request(value, pack(root=tmp_path))
    request = valid_request.model_copy(update={"evidence_pack": evidence_pack})
    result = validate_module_extraction_boundary(request, value, tmp_path)
    assert "contract.invalid" in issue_codes(result)


@pytest.mark.parametrize("link_kind", ("final", "intermediate"))
def test_source_integrity_rejects_symlink_escape(
    tmp_path: Path, link_kind: str
) -> None:
    repository_root = tmp_path / "repository"
    shutil.copytree(REPO, repository_root)
    outside = tmp_path.parent / "outside.py"
    if link_kind == "final":
        source = repository_root / "src/shop/checkout.py"
        outside.write_bytes(source.read_bytes())
        source.unlink()
        os.symlink(outside, source)
    else:
        outside_directory = tmp_path / "outside-shop"
        shutil.move(repository_root / "src/shop", outside_directory)
        os.symlink(outside_directory, repository_root / "src/shop")
    request, value = bound_fixture(repository_root)

    result = validate_module_extraction_boundary(request, value, repository_root)

    assert "source.path.escape" in issue_codes(result)


def test_secure_open_rejects_final_component_swapped_to_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repository"
    shutil.copytree(REPO, repository_root)
    source = repository_root / "src/shop/checkout.py"
    outside = tmp_path / "outside.py"
    outside.write_bytes(source.read_bytes())
    request, value = bound_fixture(repository_root)
    real_open = os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == "checkout.py" and dir_fd is not None and not swapped:
            swapped = True
            source.unlink()
            os.symlink(outside, source)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr("knowledge_compiler.validation.module.os.open", racing_open)

    result = validate_module_extraction_boundary(request, value, repository_root)

    assert swapped
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
    value = extraction()
    request = extraction_request(value, pack()).model_copy(
        update={"evidence_pack": evidence_pack}
    )
    result = validate_module_extraction_boundary(request, value, REPO)
    expected = "contract.invalid" if field in {"content_hash", "id"} else code
    assert expected in issue_codes(result)


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
    draft["scope"]["root"] = REPO
    if field == "summary":
        draft[field]["claim_ids"] = ["module.shop.checkout.claim.unknown"]
    else:
        draft[field][0]["claim_ids"] = ["module.shop.checkout.claim.unknown"]
    result = validate_module_extraction(
        ExtractionResult.model_construct(**result_data), pack(), REPO
    )
    assert "contract.invalid" in issue_codes(result)


def test_binding_rejects_unknown_evidence_missing_responsibility_and_empty_claim() -> None:
    data = load("module-extraction.json")
    data["draft"]["scope"]["root"] = REPO
    data["draft"]["claims"][0]["evidence_ids"] = ["sha256:" + "f" * 64]
    data["draft"]["claims"][1]["evidence_ids"] = []
    data["draft"]["responsibilities"] = []
    result = validate_module_extraction(
        ExtractionResult.model_construct(**data), pack(), REPO
    )
    assert "contract.invalid" in issue_codes(result)
    assert result.issues == tuple(
        sorted(result.issues, key=lambda i: (i.code, i.location, i.message))
    )


def test_binding_rejects_duplicate_responsibility_text_and_blocks_canonicalization() -> None:
    value, evidence_pack, request, verification = valid_semantic_objects()
    duplicate = value.draft.responsibilities[0]
    changed_draft = value.draft.model_copy(
        update={"responsibilities": (*value.draft.responsibilities, duplicate)}
    )
    changed = value.model_copy(update={"draft": changed_draft})

    checked = validate_module_extraction(changed, evidence_pack, REPO)
    applied = apply_verification(
        changed, evidence_pack, request, verification, REPO
    )

    assert "responsibility.duplicate" in issue_codes(checked)
    assert checked.issues == tuple(
        sorted(
            checked.issues,
            key=lambda issue: (issue.code, issue.location, issue.message),
        )
    )
    assert applied.module is None
    assert "responsibility.duplicate" in issue_codes(applied)


def test_binding_rejects_snapshot_mismatch_and_never_repairs_input() -> None:
    value = extraction()
    object.__setattr__(value, "snapshot_id", "sha256:" + "f" * 64)
    before = value.model_dump()
    result = validate_module_extraction(value, pack(), REPO)
    assert "identity.snapshot" in issue_codes(result)
    assert value.model_dump() == before


def test_rejects_byte_identical_supplied_root_that_differs_from_declared_root(
    tmp_path: Path,
) -> None:
    alternate = tmp_path / "alternate-repository"
    shutil.copytree(REPO, alternate)
    value, evidence_pack, request, verification = valid_semantic_objects()
    before = value.model_dump()

    checked = validate_module_extraction(value, evidence_pack, alternate)
    applied = apply_verification(
        value, evidence_pack, request, verification, alternate
    )

    assert issue_codes(checked) == {"identity.repository_root"}
    assert applied.module is None
    assert "identity.repository_root" in issue_codes(applied)
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


def test_apply_revalidates_copied_verification_request_and_result() -> None:
    value, evidence_pack, request, result = valid_semantic_objects()
    extraction_boundary = extraction_request(value, evidence_pack)
    bad_request_claim = request.claims[0].model_copy(
        update={"statement": "", "evidence": ()}
    )
    bad_request = request.model_copy(
        update={"claims": (bad_request_claim, *request.claims[1:])}
    )
    bad_result_claim = result.verifications[0].model_copy(
        update={"evidence_ids": (), "excerpt_hashes": (), "excerpts": ()}
    )
    bad_result = result.model_copy(
        update={"verifications": (bad_result_claim, *result.verifications[1:])}
    )

    checked = apply_verification_result(
        extraction_boundary, value, bad_request, bad_result, REPO
    )

    assert checked.module is None
    assert "contract.invalid" in issue_codes(checked)
    assert any("verification_request.claims.0.statement" in issue.location for issue in checked.issues)
    assert any("verification_result.verifications.0" in issue.location for issue in checked.issues)


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
    checked = apply_verification(value, evidence_pack, request, changed, REPO)
    assert checked.module is None
    if field == "operation":
        assert "contract.invalid" in issue_codes(checked)
    else:
        assert any(issue.code.startswith("verification.correlation") for issue in checked.issues)


@pytest.mark.parametrize("status", ("partial", "unsupported", "conflicted"))
def test_apply_rejects_every_non_supported_status(status: str) -> None:
    value, evidence_pack, request, result = valid_semantic_objects()
    first = result.verifications[0].model_copy(update={"status": status})
    changed = result.model_copy(update={"verifications": (first, *result.verifications[1:])})
    checked = apply_verification(value, evidence_pack, request, changed, REPO)
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
    checked = apply_verification(value, evidence_pack, request, changed, REPO)
    assert checked.module is None
    assert any(issue.code.startswith("verification.") for issue in checked.issues)


def test_apply_constructs_new_canonical_module_and_copies_provenance() -> None:
    value, evidence_pack, request, result = valid_semantic_objects()
    checked = apply_verification(value, evidence_pack, request, result, REPO)
    assert checked.is_valid and checked.module is not None
    assert checked.module.provenance == value.provenance
    assert checked.module.confidence == value.draft.confidence
    assert checked.module is not value.draft
    assert all(claim.verification.status == "supported" for claim in checked.module.claims)
