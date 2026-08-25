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
