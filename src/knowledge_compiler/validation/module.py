from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from knowledge_compiler.contracts.evidence import EvidencePack, build_evidence_id
from knowledge_compiler.contracts.knowledge import (
    Claim,
    ClaimVerification,
    ExtractionResult,
    ModuleKnowledge,
    Validity,
)
from knowledge_compiler.contracts.semantic import (
    ExtractionRequest,
    VerificationClaim,
    VerificationEvidence,
    VerificationRequest,
    VerificationResult,
)
from knowledge_compiler.contracts.repository import build_snapshot_id


_ORIGINAL_OS_OPEN = os.open


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    location: str
    message: str


class ModuleValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    issues: tuple[ValidationIssue, ...] = ()
    module: ModuleKnowledge | None = None

    @property
    def is_valid(self) -> bool:
        return not self.issues


class ModuleValidationError(ValueError):
    """Typed failure raised when a verification request cannot be built safely."""

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__("module validation failed: " + "; ".join(
            f"{issue.code}@{issue.location}: {issue.message}" for issue in issues
        ))


def _result(issues: list[ValidationIssue], module: ModuleKnowledge | None = None) -> ModuleValidationResult:
    ordered = tuple(
        sorted(issues, key=lambda item: (item.code, item.location, item.message))
    )
    return ModuleValidationResult(issues=ordered, module=None if ordered else module)


def _issue(issues: list[ValidationIssue], code: str, location: str, message: str) -> None:
    issues.append(ValidationIssue(code=code, location=location, message=message))


def _get(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _evidence_items(pack: EvidencePack) -> tuple[Any, ...]:
    return tuple(_get(pack, "evidence", ()))


def _safe_source_parts(raw_path: Any) -> tuple[tuple[str, ...] | None, str | None]:
    if not isinstance(raw_path, str):
        return None, "invalid"
    parsed = PurePosixPath(raw_path)
    if (
        not raw_path
        or "\x00" in raw_path
        or "\\" in raw_path
        or re.match(r"^[A-Za-z]:", raw_path)
        or parsed.is_absolute()
        or ".." in parsed.parts
        or parsed.as_posix() != raw_path
        or raw_path in {"", "."}
    ):
        return None, "invalid"
    return parsed.parts, None


def _is_symlink_at(name: str, directory_fd: int) -> bool:
    try:
        details = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISLNK(details.st_mode)


def _os_error_message(error: OSError) -> str:
    error_name = errno.errorcode.get(error.errno or 0, "UNKNOWN")
    return f"secure source open failed: {error_name}"


def _secure_read_source(
    root: Path, parts: tuple[str, ...]
) -> tuple[bytes | None, str | None, str | None]:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    supports_dir_fd = getattr(os, "supports_dir_fd", set())
    if nofollow is None or directory is None or _ORIGINAL_OS_OPEN not in supports_dir_fd:
        return None, "unsupported", "secure descriptor-relative opening is unavailable"
    descriptors: list[int] = []
    try:
        root_fd = os.open(root, os.O_RDONLY | directory | nofollow)
        descriptors.append(root_fd)
        parent_fd = root_fd
        for component in parts[:-1]:
            try:
                child_fd = os.open(
                    component,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=parent_fd,
                )
            except OSError as error:
                if error.errno in {errno.ELOOP, errno.ENOTDIR} and _is_symlink_at(
                    component, parent_fd
                ):
                    return None, "escape", "source path contains a symlink"
                if error.errno == errno.ENOENT:
                    return None, "missing", "source file does not exist"
                return None, "read", _os_error_message(error)
            descriptors.append(child_fd)
            parent_fd = child_fd
        try:
            source_fd = os.open(
                parts[-1],
                os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent_fd,
            )
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR} and _is_symlink_at(
                parts[-1], parent_fd
            ):
                return None, "escape", "source path resolves through a symlink"
            if error.errno == errno.ENOENT:
                return None, "missing", "source file does not exist"
            return None, "read", _os_error_message(error)
        descriptors.append(source_fd)
        if not stat.S_ISREG(os.fstat(source_fd).st_mode):
            return None, "not_regular", "source path does not name a regular file"
        chunks: list[bytes] = []
        while True:
            chunk = os.read(source_fd, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks), None, None
    except OSError as error:
        return None, "read", _os_error_message(error)
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _validate_sources(pack: EvidencePack, repository_root: Path, issues: list[ValidationIssue]) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    valid: dict[str, Any] = {}
    repository = _get(pack, "repository")
    repository_id = _get(repository, "repository_id")
    snapshot_id = _get(repository, "snapshot_id")
    commit = _get(repository, "commit")
    for index, item in enumerate(_evidence_items(pack)):
        location = f"evidence[{index}]"
        evidence_id = _get(item, "id")
        parts, error = _safe_source_parts(_get(item, "path"))
        if error:
            code = "source.path.escape" if error == "escape" else "source.path.invalid"
            _issue(issues, code, f"{location}.path", "source path is not safely contained by repository root")
            continue
        assert parts is not None
        original, open_error, open_message = _secure_read_source(root, parts)
        if open_error:
            code = {
                "escape": "source.path.escape",
                "missing": "source.missing",
                "not_regular": "source.not_regular",
                "unsupported": "source.secure_open.unsupported",
            }.get(open_error, "source.read")
            _issue(issues, code, f"{location}.path", open_message or open_error)
            continue
        assert original is not None
        try:
            original.decode("utf-8")
        except UnicodeDecodeError:
            _issue(issues, "source.utf8", f"{location}.path", "source file is not valid UTF-8")
            continue
        start = _get(item, "start_line")
        end = _get(item, "end_line")
        lines = original.splitlines(keepends=True)
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 1
            or end < start
            or end > len(lines)
        ):
            _issue(issues, "source.range", f"{location}.start_line", "source range must be a valid positive inclusive range")
            continue
        exact_bytes = b"".join(lines[start - 1 : end])
        actual_content_hash = "sha256:" + hashlib.sha256(exact_bytes).hexdigest()
        if _get(item, "content_hash") != actual_content_hash:
            _issue(issues, "source.content_hash", f"{location}.content_hash", "source content hash does not match exact source bytes")
        excerpt = _get(item, "excerpt")
        if not isinstance(excerpt, str):
            _issue(issues, "evidence.excerpt", f"{location}.excerpt", "model-visible excerpt must be text")
        else:
            actual_excerpt_hash = "sha256:" + hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            if _get(item, "excerpt_hash") != actual_excerpt_hash:
                _issue(issues, "evidence.excerpt_hash", f"{location}.excerpt_hash", "excerpt hash does not match exact model-visible UTF-8")
        try:
            expected_id = build_evidence_id(
                repository_id,
                snapshot_id,
                _get(item, "path"),
                _get(item, "symbol"),
                start,
                end,
                actual_content_hash,
            )
        except (TypeError, ValueError):
            expected_id = None
        if evidence_id != expected_id:
            _issue(issues, "evidence.id", f"{location}.id", "Evidence ID does not match its exact derived identity")
        if _get(item, "commit") != commit:
            _issue(issues, "evidence.commit", f"{location}.commit", "Evidence commit does not match repository snapshot")
        if evidence_id and expected_id == evidence_id and _get(item, "excerpt_hash") == (
            "sha256:" + hashlib.sha256(str(excerpt).encode("utf-8")).hexdigest()
        ) and _get(item, "content_hash") == actual_content_hash:
            valid[evidence_id] = item
    return valid


def _claim_ids_from_payload(draft: Any) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    summary = _get(draft, "summary")
    for claim_id in _get(summary, "claim_ids", ()):
        refs.append(("draft.summary", claim_id))
    for field in ("responsibilities", "public_interfaces", "dependencies", "relations"):
        for index, entry in enumerate(_get(draft, field, ())):
            for claim_id in _get(entry, "claim_ids", ()):
                refs.append((f"draft.{field}[{index}]", claim_id))
    return refs


def _validate_structure(
    extraction: ExtractionResult,
    pack: EvidencePack,
    repository_root: Path,
    issues: list[ValidationIssue],
) -> None:
    draft = _get(extraction, "draft")
    repository = _get(pack, "repository")
    target = _get(pack, "target")
    scope = _get(draft, "scope")
    if _get(extraction, "operation") != "extract":
        _issue(issues, "identity.operation", "operation", "extraction result operation must be extract")
    if _get(extraction, "target_id") != _get(target, "id") or _get(draft, "id") != _get(target, "id"):
        _issue(issues, "identity.target", "target_id", "extraction, draft, and evidence target must match")
    if _get(extraction, "snapshot_id") != _get(repository, "snapshot_id"):
        _issue(issues, "identity.snapshot", "snapshot_id", "extraction snapshot must match evidence snapshot")
    try:
        expected_snapshot_id = build_snapshot_id(
            _get(repository, "repository_id"),
            _get(repository, "commit"),
            _get(repository, "dirty"),
            _get(repository, "working_tree_hash"),
        )
    except (TypeError, ValueError):
        expected_snapshot_id = None
    if _get(repository, "snapshot_id") != expected_snapshot_id:
        _issue(issues, "identity.snapshot.derived", "evidence.repository.snapshot_id", "repository snapshot ID does not match its commit identity")
    expected_extraction_key = ":".join(
        (
            str(_get(extraction, "run_id")),
            str(_get(extraction, "target_id")),
            "extract",
            str(_get(extraction, "attempt")),
            str(_get(extraction, "snapshot_id")),
        )
    )
    if _get(extraction, "idempotency_key") != expected_extraction_key:
        _issue(issues, "identity.idempotency_key", "idempotency_key", "extraction idempotency key does not match its operation envelope")
    if _get(scope, "repository") != _get(repository, "repository_id"):
        _issue(issues, "identity.repository", "draft.scope.repository", "draft repository must match evidence repository")
    if _get(scope, "commit") != _get(repository, "commit"):
        _issue(issues, "identity.commit", "draft.scope.commit", "draft commit must match evidence commit")
    for field in ("branch", "dirty", "working_tree_hash"):
        if _get(scope, field) != _get(repository, field):
            _issue(issues, f"identity.{field}", f"draft.scope.{field}", f"draft {field} must match evidence repository")
    pack_root = _get(repository, "root")
    scope_root = _get(scope, "root")
    supplied_root = Path(repository_root).resolve()
    if pack_root is not None and scope_root is not None:
        declared_pack_root: Path | None = None
        declared_scope_root: Path | None = None
        try:
            declared_pack_root = Path(pack_root).resolve()
            declared_scope_root = Path(scope_root).resolve()
            roots_match = declared_pack_root == declared_scope_root
        except (OSError, TypeError):
            roots_match = False
        if not roots_match:
            _issue(issues, "identity.root", "draft.scope.root", "draft root must match evidence repository root")
        if (
            not roots_match
            or supplied_root != declared_pack_root
            or supplied_root != declared_scope_root
        ):
            _issue(
                issues,
                "identity.repository_root",
                "repository_root",
                "supplied repository root must match pack and draft declared roots",
            )
    else:
        _issue(
            issues,
            "identity.repository_root",
            "repository_root",
            "pack and draft must declare the supplied repository root",
        )
    claims = tuple(_get(draft, "claims", ()))
    claim_ids = [_get(claim, "id") for claim in claims]
    known_claims = set(claim_ids)
    if len(claim_ids) != len(known_claims):
        _issue(issues, "claim.id.duplicate", "draft.claims", "Claim IDs must be unique")
    evidence_ids = {_get(item, "id") for item in _evidence_items(pack)}
    if len(evidence_ids) != len(_evidence_items(pack)):
        _issue(issues, "evidence.id.duplicate", "evidence", "Evidence IDs must be unique")
    for index, claim in enumerate(claims):
        claim_id = _get(claim, "id")
        if not isinstance(claim_id, str) or not claim_id.startswith(f"{_get(draft, 'id')}.claim."):
            _issue(issues, "claim.id.membership", f"draft.claims[{index}].id", "Claim must belong to the draft Module")
        cited = tuple(_get(claim, "evidence_ids", ()))
        if not cited:
            _issue(issues, "claim.evidence.missing", f"draft.claims[{index}].evidence_ids", "Claim must cite evidence")
        for evidence_id in cited:
            if evidence_id not in evidence_ids:
                _issue(issues, "claim.evidence.unknown", f"draft.claims[{index}].evidence_ids", f"unknown Evidence ID: {evidence_id}")
    for location, claim_id in _claim_ids_from_payload(draft):
        if claim_id not in known_claims:
            _issue(issues, "claim.reference.unknown", location, f"unknown Claim ID: {claim_id}")
    if not tuple(_get(draft, "responsibilities", ())):
        _issue(issues, "responsibility.required", "draft.responsibilities", "Module requires at least one responsibility")
    responsibility_texts = [
        _get(item, "text") for item in tuple(_get(draft, "responsibilities", ()))
    ]
    if len(responsibility_texts) != len(set(responsibility_texts)):
        _issue(
            issues,
            "responsibility.duplicate",
            "draft.responsibilities",
            "responsibility text must be unique",
        )
    required_text = (
        ("draft.title", _get(draft, "title")),
        ("draft.summary.text", _get(_get(draft, "summary"), "text")),
    )
    for location, value in required_text:
        if not isinstance(value, str) or not value.strip():
            _issue(issues, "payload.required", location, "required payload text is missing or blank")
    field_requirements = {
        "responsibilities": ("text",),
        "public_interfaces": ("name", "description"),
        "dependencies": ("target", "description"),
        "relations": ("predicate", "target"),
    }
    for field, names in field_requirements.items():
        entries = tuple(_get(draft, field, ()))
        keys: list[tuple[Any, ...]] = []
        for index, entry in enumerate(entries):
            key = tuple(_get(entry, name) for name in names if name != "description" and name != "text")
            if key:
                keys.append(key)
            for name in names:
                value = _get(entry, name)
                if not isinstance(value, str) or not value.strip():
                    _issue(issues, "payload.required", f"draft.{field}[{index}].{name}", "required payload text is missing or blank")
        if keys and len(keys) != len(set(keys)):
            _issue(issues, "payload.duplicate", f"draft.{field}", "factual payload keys must be unique")


ModelT = TypeVar("ModelT", bound=BaseModel)
_ENVELOPE_FIELDS = (
    "contract_version",
    "run_id",
    "target_id",
    "operation",
    "attempt",
    "snapshot_id",
    "idempotency_key",
)


def _revalidate_model(
    model_type: type[ModelT], value: Any, boundary: str, issues: list[ValidationIssue]
) -> ModelT | None:
    try:
        return model_type.model_validate(value)
    except ValidationError as error:
        for detail in error.errors(include_url=False, include_context=False):
            suffix = ".".join(str(part) for part in detail["loc"])
            location = boundary if not suffix else f"{boundary}.{suffix}"
            _issue(issues, "contract.invalid", location, detail["msg"])
        return None


def _validated_extraction_context(
    request: ExtractionRequest,
    extraction: ExtractionResult,
    repository_root: Path,
) -> tuple[ExtractionRequest | None, ExtractionResult | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    validated_request = _revalidate_model(
        ExtractionRequest, request, "extraction_request", issues
    )
    validated_extraction = _revalidate_model(
        ExtractionResult, extraction, "extraction_result", issues
    )
    if validated_request is None or validated_extraction is None:
        return validated_request, validated_extraction, issues
    # Revalidate the nested pack explicitly at this public trust boundary.
    validated_pack = _revalidate_model(
        EvidencePack,
        validated_request.evidence_pack,
        "extraction_request.evidence_pack",
        issues,
    )
    if validated_pack is None:
        return validated_request, validated_extraction, issues
    validated_request = validated_request.model_copy(
        update={"evidence_pack": validated_pack}
    )
    mismatched = [
        field
        for field in _ENVELOPE_FIELDS
        if getattr(validated_request, field) != getattr(validated_extraction, field)
    ]
    for field in mismatched:
        _issue(
            issues,
            "extraction.correlation",
            field,
            f"extraction result {field} does not echo extraction request",
        )
    _validate_structure(
        validated_extraction,
        validated_pack,
        repository_root,
        issues,
    )
    _validate_sources(validated_pack, repository_root, issues)
    return validated_request, validated_extraction, issues


def validate_module_extraction(
    request: ExtractionRequest,
    extraction: ExtractionResult,
    repository_root: Path,
) -> ModuleValidationResult:
    _, _, issues = _validated_extraction_context(
        request, extraction, repository_root
    )
    return _result(issues)


def _verification_digest(claims: tuple[VerificationClaim, ...]) -> str:
    payload = [
        {
            "claim_id": claim.claim_id,
            "statement": claim.statement,
            "evidence": [[entry.evidence_id, entry.excerpt_hash] for entry in claim.evidence],
        }
        for claim in sorted(claims, key=lambda item: item.claim_id)
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _verification_key(extraction: ExtractionResult) -> str:
    return ":".join(
        (
            extraction.run_id,
            extraction.target_id,
            "verify",
            str(extraction.attempt),
            extraction.snapshot_id,
        )
    )


def build_verification_request(
    extraction_request: ExtractionRequest,
    extraction: ExtractionResult,
    repository_root: Path,
) -> VerificationRequest:
    validated_request, validated_extraction, issues = _validated_extraction_context(
        extraction_request, extraction, repository_root
    )
    if issues or validated_request is None or validated_extraction is None:
        raise ModuleValidationError(_result(issues).issues)
    evidence_pack = validated_request.evidence_pack
    extraction = validated_extraction
    evidence_by_id = {item.id: item for item in evidence_pack.evidence}
    claims = tuple(
        VerificationClaim(
            claim_id=claim.id,
            statement=claim.statement,
            evidence=tuple(
                VerificationEvidence(
                    evidence_id=evidence_id,
                    excerpt_hash=evidence_by_id[evidence_id].excerpt_hash,
                    excerpt=evidence_by_id[evidence_id].excerpt,
                )
                for evidence_id in claim.evidence_ids
            ),
        )
        for claim in extraction.draft.claims
    )
    return VerificationRequest(
        contract_version=extraction.contract_version,
        run_id=extraction.run_id,
        target_id=extraction.target_id,
        operation="verify",
        attempt=extraction.attempt,
        snapshot_id=extraction.snapshot_id,
        idempotency_key=_verification_key(extraction),
        claims=claims,
        verification_request_digest=_verification_digest(claims),
    )


def apply_verification_result(
    extraction_request: ExtractionRequest,
    extraction: ExtractionResult,
    request: VerificationRequest,
    verification_result: VerificationResult,
    repository_root: Path,
) -> ModuleValidationResult:
    validated_extraction_request, validated_extraction, issues = (
        _validated_extraction_context(
            extraction_request, extraction, repository_root
        )
    )
    validated_verification_request = _revalidate_model(
        VerificationRequest,
        request,
        "verification_request",
        issues,
    )
    validated_verification_result = _revalidate_model(
        VerificationResult,
        verification_result,
        "verification_result",
        issues,
    )
    if (
        issues
        or validated_extraction_request is None
        or validated_extraction is None
        or validated_verification_request is None
        or validated_verification_result is None
    ):
        return _result(issues)
    try:
        expected_request = build_verification_request(
            validated_extraction_request,
            validated_extraction,
            repository_root,
        )
    except ModuleValidationError as error:
        return _result([*issues, *error.issues])
    extraction = validated_extraction
    request = validated_verification_request
    verification_result = validated_verification_result
    for field in (
        "contract_version", "run_id", "target_id", "operation", "attempt",
        "snapshot_id", "idempotency_key", "verification_request_digest",
    ):
        if getattr(request, field) != getattr(expected_request, field):
            _issue(issues, "verification.correlation.request", field, f"verification request {field} is stale or mismatched")
        if getattr(verification_result, field) != getattr(request, field):
            _issue(issues, "verification.correlation.result", field, f"verification result {field} does not echo request")
    if request.claims != expected_request.claims:
        _issue(issues, "verification.correlation.request", "claims", "verification request does not contain the exact draft Claim bindings")
    expected_by_id = {claim.claim_id: claim for claim in expected_request.claims}
    actual_by_id = {item.claim_id: item for item in verification_result.verifications}
    if len(actual_by_id) != len(verification_result.verifications):
        _issue(issues, "verification.claim.duplicate", "verifications", "verification Claim IDs must be unique")
    for claim_id in sorted(set(expected_by_id) - set(actual_by_id)):
        _issue(issues, "verification.claim.missing", claim_id, "required Claim verification is missing")
    for claim_id in sorted(set(actual_by_id) - set(expected_by_id)):
        _issue(issues, "verification.claim.unknown", claim_id, "verification contains an unknown Claim")
    for claim_id in sorted(set(expected_by_id) & set(actual_by_id)):
        expected = expected_by_id[claim_id]
        actual = actual_by_id[claim_id]
        if actual.status != "supported":
            _issue(issues, "verification.status", claim_id, f"Claim is {actual.status}, not supported")
        if actual.verification_request_digest != request.verification_request_digest:
            _issue(issues, "verification.claim.digest", claim_id, "Claim verification digest does not echo request")
        expected_ids = tuple(entry.evidence_id for entry in expected.evidence)
        expected_hashes = tuple(entry.excerpt_hash for entry in expected.evidence)
        expected_excerpts = tuple(entry.excerpt for entry in expected.evidence)
        if actual.evidence_ids != expected_ids:
            _issue(issues, "verification.evidence.ids", claim_id, "verified Evidence IDs differ from requested bindings")
        if actual.excerpt_hashes != expected_hashes:
            _issue(issues, "verification.evidence.hashes", claim_id, "verified excerpt hashes differ from requested bindings")
        if actual.excerpts != expected_excerpts:
            _issue(issues, "verification.evidence.excerpts", claim_id, "verified redacted excerpts differ from requested text")
    if issues:
        return _result(issues)
    draft_claims = {claim.id: claim for claim in extraction.draft.claims}
    try:
        claims = tuple(
            Claim.model_validate(
                {
                    **draft_claims[claim_id].model_dump(),
                    "verification": ClaimVerification(
                        status=actual_by_id[claim_id].status,
                        verifier=actual_by_id[claim_id].verifier,
                        evidence_ids=actual_by_id[claim_id].evidence_ids,
                        excerpt_hashes=actual_by_id[claim_id].excerpt_hashes,
                        verification_request_digest=request.verification_request_digest,
                    ),
                }
            )
            for claim_id in sorted(draft_claims)
        )
        draft_payload = extraction.draft.model_dump()
        module = ModuleKnowledge.model_validate(
            {
                **draft_payload,
                "scope": draft_payload["scope"],
                "claims": claims,
                "confidence": extraction.draft.confidence,
                "provenance": extraction.provenance,
                "validity": Validity(
                    status="verified",
                    verified_commit=extraction.draft.scope.commit,
                    validation_report=("source-integrity", "structural", "semantic"),
                ),
            }
        )
    except ValidationError as error:
        for detail in error.errors(include_url=False, include_context=False):
            suffix = ".".join(str(part) for part in detail["loc"])
            _issue(
                issues,
                "contract.invalid",
                "canonical_module" if not suffix else f"canonical_module.{suffix}",
                detail["msg"],
            )
        return _result(issues)
    return _result([], module)


__all__ = [
    "ModuleValidationResult",
    "ModuleValidationError",
    "ValidationIssue",
    "apply_verification_result",
    "build_verification_request",
    "validate_module_extraction",
]
