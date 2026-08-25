from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from knowledge_compiler.contracts import (
    EvidenceBudget,
    PlanTarget,
)
from knowledge_compiler.contracts.knowledge import ExtractionResult
from knowledge_compiler.contracts.semantic import (
    ExtractionRequest,
    VerificationResult,
)
from knowledge_compiler.providers.fake import FakeEvidenceProvider
from knowledge_compiler.storage import GenerationPublisher, PublicationError
from knowledge_compiler.validation.module import (
    ModuleValidationError,
    apply_verification_result,
    build_verification_request,
)


DEFAULT_BUDGET = EvidenceBudget(max_items=8, max_characters=4000, max_tokens=512)

FIXTURE_TARGET = PlanTarget(
    id="module.shop.checkout",
    topic="CheckoutService",
    evidence_seeds=("CheckoutService", "Inventory.reserve"),
)


@dataclass(frozen=True)
class SliceSuccess:
    generation: str
    object_id: str
    canonical_path: Path
    card_path: Path
    wiki_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class SliceFailure:
    reason: str
    message: str
    issues: tuple[str, ...] = ()


def _load_semantic_json(path: Path) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"invalid {path.name} JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _summarize_validation(error: ValidationError) -> str:
    parts: list[str] = []
    for detail in error.errors(include_url=False, include_context=False)[:10]:
        location = ".".join(str(part) for part in detail["loc"]) or "<root>"
        parts.append(f"{location}: {detail['msg']}")
    return "contract validation failed: " + "; ".join(parts)


def _issue_strings(issues: Any) -> tuple[str, ...]:
    return tuple(
        f"{issue.code}@{issue.location}: {issue.message}" for issue in issues
    )


def _parse_extraction(
    path: Path, snapshot_root: Path
) -> ExtractionResult | SliceFailure:
    try:
        payload = _load_semantic_json(path)
    except (OSError, ValueError) as error:
        return SliceFailure("extraction.parse", str(error))
    try:
        # The fixture uses "." as its portable root marker, mirroring the
        # evidence-pack convention the fake provider binds at load time.
        payload["draft"]["scope"]["root"] = str(snapshot_root)
        return ExtractionResult.model_validate(payload)
    except ValidationError as error:
        return SliceFailure("extraction.contract", _summarize_validation(error))
    except (KeyError, TypeError, ValueError) as error:
        return SliceFailure(
            "extraction.contract", str(error) or type(error).__name__
        )


def _parse_verification(path: Path) -> VerificationResult | SliceFailure:
    try:
        payload = _load_semantic_json(path)
    except (OSError, ValueError) as error:
        return SliceFailure("verification.parse", str(error))
    try:
        return VerificationResult.model_validate(payload)
    except ValidationError as error:
        return SliceFailure("verification.contract", _summarize_validation(error))
    except (TypeError, ValueError) as error:
        return SliceFailure(
            "verification.contract", str(error) or type(error).__name__
        )


def _generation_id(extraction: ExtractionResult, module: Any) -> str:
    identity = ":".join(
        (
            extraction.run_id,
            extraction.target_id,
            extraction.snapshot_id,
            str(extraction.attempt),
        )
    )
    content = json.dumps(
        module.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256((identity + "\n" + content).encode("utf-8")).hexdigest()
    return "gen-" + digest[:32]


def run_fake_module_slice(
    provider: FakeEvidenceProvider,
    extraction_path: str | os.PathLike[str],
    verification_path: str | os.PathLike[str],
    output_root: str | os.PathLike[str],
    *,
    budget: EvidenceBudget | None = None,
    fault_injector: Callable[[str], None] | None = None,
) -> SliceSuccess | SliceFailure:
    """Drive one fixture Module from bounded evidence to one publication."""

    try:
        snapshot = provider.bound_repository()
        provider.ensure_index(snapshot)
        survey = provider.inspect(snapshot)
        missing = [
            seed
            for seed in FIXTURE_TARGET.evidence_seeds
            if seed not in survey.symbols
        ]
        if missing:
            return SliceFailure(
                "target.selection",
                "survey does not mention target evidence seeds: "
                + ", ".join(missing),
            )
        pack = provider.build_pack(snapshot, FIXTURE_TARGET, budget or DEFAULT_BUDGET)
    except (ValueError, KeyError) as error:
        return SliceFailure("provider", str(error))

    extraction = _parse_extraction(Path(extraction_path), snapshot.root)
    if isinstance(extraction, SliceFailure):
        return extraction

    try:
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
    except ValidationError as error:
        return SliceFailure("extraction.contract", _summarize_validation(error))

    try:
        verification_request = build_verification_request(
            request, extraction, snapshot.root
        )
    except ModuleValidationError as error:
        return SliceFailure(
            "validation",
            "structural or source-integrity validation failed",
            _issue_strings(error.issues),
        )

    verification = _parse_verification(Path(verification_path))
    if isinstance(verification, SliceFailure):
        return verification

    try:
        verified = apply_verification_result(
            request,
            extraction,
            verification_request,
            verification,
            snapshot.root,
        )
    except (ModuleValidationError, ValidationError) as error:
        return SliceFailure(
            "verification",
            "semantic verification could not be applied",
            _issue_strings(getattr(error, "issues", ()))
            or (str(error),),
        )
    if not verified.is_valid or verified.module is None:
        return SliceFailure(
            "verification",
            "semantic verification rejected the draft",
            _issue_strings(verified.issues),
        )

    publisher = GenerationPublisher(output_root, fault_injector=fault_injector)
    try:
        published = publisher.publish(
            _generation_id(extraction, verified.module), verified.module, pack
        )
    except PublicationError as error:
        try:
            publisher.recover()
        except PublicationError as recovery_error:
            return SliceFailure(
                "recovery",
                f"publication failed ({error}) and recovery failed "
                f"({recovery_error})",
            )
        return SliceFailure("publication", str(error))
    return SliceSuccess(
        generation=published.generation,
        object_id=verified.module.id,
        canonical_path=published.canonical_path,
        card_path=published.card_path,
        wiki_path=published.wiki_path,
        manifest_path=published.manifest_path,
    )


app = typer.Typer(
    help="Run the fake-provider Module vertical slice (test-only harness)."
)


@app.command()
def main(
    repository_root: Annotated[Path, typer.Option(help="Fixture repository root")],
    fixtures: Annotated[Path, typer.Option(help="Fake provider fixture directory")],
    extraction: Annotated[Path, typer.Option(help="Extraction result JSON")],
    verification: Annotated[Path, typer.Option(help="Verification result JSON")],
    output_root: Annotated[Path, typer.Option(help="Publication output root")],
) -> None:
    try:
        fake = FakeEvidenceProvider(
            fixture_dir=fixtures, repository_root=repository_root
        )
    except (OSError, ValueError) as error:
        typer.secho(f"provider failure: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    outcome = run_fake_module_slice(fake, extraction, verification, output_root)
    if isinstance(outcome, SliceFailure):
        typer.secho(f"{outcome.reason}: {outcome.message}", fg=typer.colors.RED)
        for issue in outcome.issues:
            typer.secho(f"  - {issue}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.echo(
        f"published {outcome.object_id} generation {outcome.generation}"
    )
    for path in (
        outcome.canonical_path,
        outcome.card_path,
        outcome.wiki_path,
        outcome.manifest_path,
    ):
        typer.echo(str(path))


__all__ = [
    "DEFAULT_BUDGET",
    "SliceFailure",
    "SliceSuccess",
    "app",
    "run_fake_module_slice",
]
