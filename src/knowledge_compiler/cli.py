from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

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


__all__ = ["app"]


def _load_existing_language(path: Path) -> str | None:
    try:
        return str(yaml.safe_load(path.read_text(encoding="utf-8")).get("language"))
    except (OSError, ValueError, yaml.YAMLError, AttributeError):
        return None
