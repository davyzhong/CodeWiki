from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from pydantic import ValidationError

from knowledge_compiler.compiler import (
    compile_module_card,
    compile_module_wiki,
    compile_module_yaml,
)
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

_MESSAGE_LIMIT = 2000
_ISSUE_LIMIT = 20
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


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


def _terminal_safe(text: str) -> str:
    return _CONTROL_CHARACTERS.sub(" ", text)


def _echo_failure(text: str) -> None:
    typer.secho(_terminal_safe(_bounded(text)), fg=typer.colors.RED)


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
    except (json.JSONDecodeError, OSError, UnicodeError, ValueError, RecursionError) as error:
        raise ValueError(
            f"invalid {path.name} JSON: {_bounded(str(error))}"
        ) from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _bounded(text: str) -> str:
    if len(text) > _MESSAGE_LIMIT:
        return text[:_MESSAGE_LIMIT] + f"…[truncated {len(text) - _MESSAGE_LIMIT} chars]"
    return text


def _failure(
    reason: str, message: str, issues: tuple[str, ...] = ()
) -> SliceFailure:
    return SliceFailure(reason, _bounded(message), issues)


def _summarize_validation(error: ValidationError) -> str:
    parts: list[str] = []
    for detail in error.errors(include_url=False, include_context=False)[:10]:
        location = ".".join(str(part) for part in detail["loc"]) or "<root>"
        parts.append(_bounded(f"{location}: {detail['msg']}"))
    return "contract validation failed: " + "; ".join(parts)


def _issue_strings(issues: Any) -> tuple[str, ...]:
    rendered = [_bounded(f"{issue.code}@{issue.location}: {issue.message}") for issue in issues]
    if len(rendered) > _ISSUE_LIMIT:
        omitted = len(rendered) - _ISSUE_LIMIT
        rendered = rendered[:_ISSUE_LIMIT] + [f"…and {omitted} more issues"]
    return tuple(rendered)


def _parse_extraction(
    path: Path, snapshot_root: Path
) -> ExtractionResult | SliceFailure:
    try:
        payload = _load_semantic_json(path)
    except (OSError, ValueError) as error:
        return _failure("extraction.parse", str(error))
    try:
        # The fixture uses "." as its portable root marker, mirroring the
        # evidence-pack convention the fake provider binds at load time.
        payload["draft"]["scope"]["root"] = str(snapshot_root)
        return ExtractionResult.model_validate(payload)
    except ValidationError as error:
        return _failure("extraction.contract", _summarize_validation(error))
    except (KeyError, TypeError, ValueError) as error:
        return _failure(
            "extraction.contract", str(error) or type(error).__name__
        )


def _parse_verification(path: Path) -> VerificationResult | SliceFailure:
    try:
        payload = _load_semantic_json(path)
    except (OSError, ValueError) as error:
        return _failure("verification.parse", str(error))
    try:
        return VerificationResult.model_validate(payload)
    except ValidationError as error:
        return _failure("verification.contract", _summarize_validation(error))
    except (TypeError, ValueError) as error:
        return _failure(
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


def _is_committed(
    output_root: Path, generation: str, module: Any, pack: Any
) -> bool:
    """A generation counts as committed only when the manifest marker matches
    and every published file is a regular, non-symlink file whose bytes equal
    what this run would publish; anything else fails closed."""

    knowledge = Path(output_root).absolute() / ".knowledge"
    manifest_path = knowledge / "manifest.yaml"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        return False
    try:
        value = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return False
    active = value.get("active_generation") if isinstance(value, dict) else None
    if active != generation:
        return False
    try:
        expected = {
            "canonical": compile_module_yaml(module, pack),
            "card": compile_module_card(module, pack),
            "wiki": compile_module_wiki(module, pack),
            # The wiki stamp is owned by `knowledge compile`; the slice
            # replay accepts whatever stamp the publisher preserved.
            "manifest": yaml.safe_dump(
                {
                    "active_generation": generation,
                    "agent_views_generation": generation,
                    "wiki_generation": (
                        value.get("wiki_generation")
                        if isinstance(value, dict)
                        else None
                    ),
                },
                sort_keys=False,
                allow_unicode=True,
            ).encode("utf-8"),
        }
    except Exception:
        return False
    object_id = module.id
    destinations = {
        "canonical": knowledge / f"objects/modules/{object_id}.yaml",
        "card": knowledge / f"views/cards/{object_id}.md",
        "wiki": knowledge / f"views/wiki/modules/{object_id}.md",
        "manifest": manifest_path,
    }
    for name, destination in destinations.items():
        try:
            if destination.is_symlink() or not destination.is_file():
                return False
            if destination.read_bytes() != expected[name]:
                return False
        except OSError:
            return False
    return True


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
            return _failure(
                "target.selection",
                "survey does not mention target evidence seeds: "
                + ", ".join(missing),
            )
        pack = provider.build_pack(snapshot, FIXTURE_TARGET, budget or DEFAULT_BUDGET)
    except (ValueError, KeyError) as error:
        return _failure("provider", str(error))

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
        return _failure("extraction.contract", _summarize_validation(error))

    try:
        verification_request = build_verification_request(
            request, extraction, snapshot.root
        )
    except ModuleValidationError as error:
        return _failure(
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
    except ModuleValidationError as error:
        return _failure(
            "verification",
            "semantic verification could not be applied",
            _issue_strings(error.issues),
        )
    except ValidationError as error:
        return _failure(
            "verification",
            "semantic verification could not be applied",
            (_summarize_validation(error),),
        )
    if not verified.is_valid or verified.module is None:
        return _failure(
            "verification",
            "semantic verification rejected the draft",
            _issue_strings(verified.issues),
        )

    publisher = GenerationPublisher(output_root, fault_injector=fault_injector)
    generation = _generation_id(extraction, verified.module)
    try:
        published = publisher.publish(generation, verified.module, pack)
    except PublicationError as error:
        try:
            publisher.recover()
        except PublicationError as recovery_error:
            publication_detail = str(error)
            recovery_detail = str(recovery_error)
            if recovery_detail == publication_detail:
                detail = publication_detail
            else:
                detail = (
                    f"publication failed ({publication_detail}) and recovery "
                    f"failed ({recovery_detail})"
                )
            return _failure("recovery", detail)
        # A post-commit cleanup crash leaves the generation fully committed;
        # recovery confirms the manifest marker, so report it as published.
        if _is_committed(Path(output_root), generation, verified.module, pack):
            knowledge = Path(output_root).absolute() / ".knowledge"
            object_id = verified.module.id
            return SliceSuccess(
                generation=generation,
                object_id=object_id,
                canonical_path=knowledge / f"objects/modules/{object_id}.yaml",
                card_path=knowledge / f"views/cards/{object_id}.md",
                wiki_path=knowledge / f"views/wiki/modules/{object_id}.md",
                manifest_path=knowledge / "manifest.yaml",
            )
        return _failure("publication", str(error))
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
        _echo_failure(f"provider failure: {error}")
        raise typer.Exit(code=1) from None

    outcome = run_fake_module_slice(fake, extraction, verification, output_root)
    if isinstance(outcome, SliceFailure):
        _echo_failure(f"{outcome.reason}: {outcome.message}")
        for issue in outcome.issues:
            _echo_failure(f"  - {issue}")
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
