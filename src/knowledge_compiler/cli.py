from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from knowledge_compiler.config import KnowledgeConfig, load_config, write_config


app = typer.Typer(help="Knowledge Compiler repository tooling.")

_MANAGED_IGNORE_MARKER = "# knowledge-compiler managed"
_MANAGED_IGNORE_ENTRIES = (
    ".knowledge/cache/",
    ".knowledge/state/",
    ".knowledge/exports/",
    ".codewiki/",
)


def _default_config(language: str) -> KnowledgeConfig:
    return KnowledgeConfig.model_validate(
        {
            "schema_version": "0.1",
            "repository_provider": "local-git",
            "evidence_provider": "codewiki",
            "language": language,
            "worker_profiles": {
                "extraction_profile": "extraction-v1",
                "validation_profile": None,
            },
            "exclusions": [],
            "scope_limits": {"max_files": 10000, "max_bytes": 52428800},
            "default_context_budget": 6000,
        }
    )


def _update_gitignore(root: Path) -> None:
    gitignore = root / ".gitignore"
    existing = (
        gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    )
    if _MANAGED_IGNORE_MARKER in existing:
        return
    addition = "\n".join(
        [_MANAGED_IGNORE_MARKER, *_MANAGED_IGNORE_ENTRIES]
    )
    separator = "" if not existing.strip() else (
        "" if existing.endswith("\n") else "\n"
    )
    gitignore.write_text(
        existing + separator + addition + "\n", encoding="utf-8"
    )


@app.command()
def build(
    executor: Annotated[str, typer.Option()] = "llm",
    repository_root: Annotated[Path, typer.Option()] = Path("."),
    report_validation_profile: Annotated[bool, typer.Option()] = False,
) -> None:
    """Run the full build through the orchestrator (exit 0/1/2)."""

    from knowledge_compiler.preflight import PreflightFailure, run_preflight

    if report_validation_profile:
        result = run_preflight(None, dry_run=True)
        typer.echo(
            "validation-profile: " + result["validation_profile_mode"]
        )
    try:
        run_preflight(repository_root.resolve())
    except PreflightFailure as error:
        typer.secho(f"preflight: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    typer.secho(
        "build: no runnable targets configured for this repository yet; "
        "wire the planner into the orchestrator CLI in the follow-up",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


@app.command()
def validate() -> None:
    """Validate the canonical store consistency (exit 0/1)."""

    import yaml

    knowledge = Path(".knowledge")
    manifest_path = knowledge / "manifest.yaml"
    if not manifest_path.is_file():
        typer.secho(
            "validate: no committed generation found", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)
    try:
        manifest = yaml.safe_load(manifest_path.read_bytes())
    except (OSError, ValueError) as error:
        typer.secho(f"validate: manifest unreadable: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    generations = {
        "active_generation",
        "agent_views_generation",
        "wiki_generation",
    }
    values = {key: manifest.get(key) for key in generations}
    if any(value is None for value in values.values()) or len(set(values.values())) != 1:
        typer.secho(
            "validate: generation markers disagree: " + json_dumps(values),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    expected_files = [
        knowledge / "objects/modules/module.shop.checkout.yaml",
        knowledge / "views/cards/module.shop.checkout.md",
        knowledge / "views/wiki/module.shop.checkout.md",
    ]
    missing = [str(path) for path in expected_files if not path.is_file()]
    if missing:
        typer.secho(
            "validate: missing published files: " + ", ".join(missing),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    typer.echo(f"validate: generation {values['active_generation']} consistent")


def json_dumps(payload: dict) -> str:
    import json as _json

    return _json.dumps(payload, sort_keys=True)


from knowledge_compiler import cli_agent_queue as _agent_queue  # noqa: E402
from knowledge_compiler.cli_agent_queue import (  # noqa: E402,F401
    evidence as _agent_evidence,
    finalize as _agent_finalize,
    next_work as _agent_next,
    prepare as _agent_prepare,
    submit_extraction as _agent_submit_extraction,
    submit_verification as _agent_submit_verification,
    verify_next as _agent_verify_next,
)

app.command(name="prepare", hidden=True)(_agent_prepare)
app.command(name="next", hidden=True)(_agent_next)
app.command(name="evidence", hidden=True)(_agent_evidence)
app.command(name="submit-extraction", hidden=True)(_agent_submit_extraction)
app.command(name="verify-next", hidden=True)(_agent_verify_next)
app.command(name="submit-verification", hidden=True)(_agent_submit_verification)
app.command(name="finalize", hidden=True)(_agent_finalize)


@app.callback()
def _main() -> None:
    """Knowledge Compiler repository tooling."""


@app.command()
def init(
    language: Annotated[str, typer.Option(help="Output language zh|en")],
    repository_root: Annotated[
        Path, typer.Option(help="Repository root (defaults to cwd)")
    ] = Path("."),
) -> None:
    if language not in {"zh", "en"}:
        typer.secho(f"unsupported language: {language}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    root = repository_root.resolve()
    knowledge = root / ".knowledge"
    config_path = knowledge / "config.yaml"

    if config_path.exists():
        try:
            existing = load_config(config_path)
        except ValueError as error:
            typer.secho(f"existing config is invalid: {error}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        if existing.language != language:
            typer.secho(
                "refusing to overwrite user configuration: configured "
                f"language is {existing.language}, requested {language}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        typer.echo(f"knowledge already initialized ({language})")
    else:
        knowledge.mkdir(parents=True, exist_ok=True)
        write_config(config_path, _default_config(language))
        typer.echo(f"initialized {config_path}")

    _update_gitignore(root)


@app.command()
def realslice(
    repository_root: Annotated[Path, typer.Option(help="Local Git repository root")],
    output_root: Annotated[Path, typer.Option(help="Publication output root")],
    config_path: Annotated[
        Path | None, typer.Option(help="Optional .knowledge/config.yaml")
    ] = None,
) -> None:
    """Run the real-provider module slice (live CodeWiki + LiteLLM)."""

    import os

    from knowledge_compiler.providers.codewiki import CodeWikiEvidenceProvider
    from knowledge_compiler.providers.codewiki_cli import CodewikiRunner
    from knowledge_compiler.real_slice import run_real_module_slice
    from knowledge_compiler.workers.litellm_worker import LiteLLMWorker

    extraction_model = os.environ.get("KNOWLEDGE_EXTRACTION_MODEL")
    if not extraction_model:
        typer.secho(
            "model failure: KNOWLEDGE_EXTRACTION_MODEL is not configured",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    def transport(*, system: str, user: str, model: str) -> str:
        import litellm

        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    provider = CodeWikiEvidenceProvider(
        CodewikiRunner(), repository_root=repository_root.resolve()
    )
    worker = LiteLLMWorker(
        transport=transport, extraction_model=extraction_model
    )
    outcome = run_real_module_slice(
        repository_root=repository_root.resolve(),
        evidence_provider=provider,
        worker=worker,
        output_root=output_root,
        config_path=config_path,
    )
    if getattr(outcome, "reason", None):
        typer.secho(
            f"{outcome.reason}: {_short(outcome.message)}", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)
    typer.echo(f"published {outcome.object_id} generation {outcome.generation}")
    typer.echo(str(outcome.manifest_path))


def _short(text: str) -> str:
    return text[:2000]


__all__ = ["app"]
