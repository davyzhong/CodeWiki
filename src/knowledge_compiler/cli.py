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

    if executor not in {"llm", "agent"}:
        typer.secho(
            f"build: unsupported executor {executor!r}; expected llm or agent",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    root = repository_root.resolve()
    config_path = root / ".knowledge/config.yaml"
    from knowledge_compiler.preflight import PreflightFailure, run_preflight

    if report_validation_profile:
        result = run_preflight(None, dry_run=True)
        typer.echo(
            "validation-profile: " + result["validation_profile_mode"]
        )
    try:
        preflight = run_preflight(root, config_path=config_path)
    except PreflightFailure as error:
        typer.secho(f"preflight: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    try:
        config = load_config(config_path)
        from knowledge_compiler.building import run_configured_build

        outcome = run_configured_build(
            repository_root=root,
            executor=executor,
            config=config,
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(f"build: {_short(str(error))}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    report_path = root / ".knowledge/state/runs/last-build.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json

    report_path.write_text(
        _json.dumps(
            {
                "status": outcome.status,
                "generation": outcome.generation,
                "published_object_ids": list(outcome.published_object_ids),
                "diagnostics": list(outcome.diagnostics),
                "run_id": outcome.run_id,
                "executor": executor,
                "validation_profile_mode": preflight[
                    "validation_profile_mode"
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    typer.echo(
        f"build: {outcome.status} generation={outcome.generation} "
        f"run={outcome.run_id}"
    )
    if outcome.status == "complete":
        return
    raise typer.Exit(code=2 if outcome.status == "partial" else 1)


@app.command()
def status(
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Report canonical object states and target results separately."""

    import json as _json

    knowledge = repository_root / ".knowledge"
    report: dict = {
        "canonical_objects": [],
        "target_results": [],
        "snapshots": {},
        "view_generations": {},
    }
    runs_root = knowledge / "state/runs"
    if runs_root.is_dir():
        from knowledge_compiler.orchestrator.contracts import RunRecord
        from knowledge_compiler.orchestrator.store import RunStore

        records: list[RunRecord] = RunStore(runs_root)._list_runs()
        record = next(
            (item for item in records if item.active),
            records[-1] if records else None,
        )
        if record is not None:
            report["run_id"] = record.run_id
            report["run_active"] = record.active
            for target in sorted(
                record.targets, key=lambda item: item.target_id
            ):
                report["target_results"].append(
                    {
                        "target_id": target.target_id,
                        "state": target.state.value,
                        "result": (
                            target.result.value if target.result else None
                        ),
                        "published_object_id": target.published_object_id,
                        "required": target.required,
                    }
                )
    manifest_path = knowledge / "manifest.yaml"
    if manifest_path.is_file():
        import yaml as _yaml

        try:
            manifest = _yaml.safe_load(manifest_path.read_bytes())
            for key in (
                "active_generation",
                "agent_views_generation",
                "wiki_generation",
            ):
                report["view_generations"][key] = manifest.get(key)
        except (OSError, ValueError):
            report["view_generations"]["error"] = "manifest unreadable"
    else:
        report["view_generations"]["error"] = "no committed generation"

    objects_root = knowledge / "objects"
    if objects_root.is_dir():
        import yaml as _yaml_objects

        for path in sorted(objects_root.rglob("*.yaml")):
            try:
                payload = _yaml_objects.safe_load(path.read_bytes())
                report["canonical_objects"].append(
                    {
                        "id": payload.get("id"),
                        "type": payload.get("type"),
                        "validity": payload.get("validity", {}).get("status"),
                    }
                )
            except (OSError, ValueError):
                report["canonical_objects"].append(
                    {"path": str(path), "error": "unreadable"}
                )

    typer.echo(_json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


@app.command(name="compile")
def compile_knowledge_views(
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Retry deterministic view compilation without changing canonical IR."""

    root = repository_root.resolve()
    manifest_path = root / ".knowledge/manifest.yaml"
    if not manifest_path.is_file():
        typer.secho(
            "compile: no committed generation found",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    from knowledge_compiler.compiler.wiki import (
        WikiCompilationError,
        compile_repository_wiki,
    )
    from knowledge_compiler.retrieval.context import (
        ContextRetrievalError,
        build_knowledge_index,
    )

    try:
        result = compile_repository_wiki(root)
        index = build_knowledge_index(root)
    except (WikiCompilationError, ContextRetrievalError) as error:
        typer.secho(f"compile: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    import json as _json

    typer.echo(
        _json.dumps(
            {
                "generation": result.generation,
                "pages": list(result.pages),
                "html": str(
                    result.html_path.relative_to(root)
                ),
                "stale_object_ids": list(result.stale_object_ids),
                "orphaned_overlay_ids": list(result.orphaned_overlay_ids),
                "index_verified_object_ids": list(index.verified_object_ids),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


@app.command(name="context")
def context_for_task(
    task: Annotated[str, typer.Argument()],
    format: Annotated[str, typer.Option()] = "markdown",
    budget: Annotated[int, typer.Option()] = 6000,
    include_stale: Annotated[bool, typer.Option("--include-stale")] = False,
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Compile budgeted task context from verified knowledge."""

    root = repository_root.resolve()
    manifest_path = root / ".knowledge/manifest.yaml"
    if not manifest_path.is_file():
        typer.secho("knowledge_update_required", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if format not in {"markdown", "json"}:
        typer.secho(
            f"context: unsupported format {format!r}", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)
    from knowledge_compiler.retrieval.context import (
        ContextRetrievalError,
        retrieve_task_context,
    )

    try:
        markdown = retrieve_task_context(
            root,
            task,
            budget=budget,
            include_stale=include_stale,
        )
    except ContextRetrievalError as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    if format == "json":
        import json as _json

        typer.echo(
            _json.dumps(
                {"task": task, "markdown": markdown},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return
    typer.echo(markdown)


@app.command(name="open")
def open_knowledge_wiki(
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Open the human Wiki, warning when it lags the active generation."""

    root = repository_root.resolve()
    html_path = root / ".knowledge/exports/repo-wiki.html"
    manifest_path = root / ".knowledge/manifest.yaml"
    if manifest_path.is_file():
        import yaml as _yaml

        try:
            manifest = _yaml.safe_load(manifest_path.read_bytes())
        except (OSError, ValueError):
            manifest = None
        if isinstance(manifest, dict) and manifest.get("wiki_generation") != (
            manifest.get("active_generation")
        ):
            typer.secho(
                "open: the Wiki lags the active generation; "
                "run knowledge compile for current views",
                fg=typer.colors.YELLOW,
            )
    if not html_path.is_file():
        typer.secho(
            "open: compiled HTML Wiki not found; run knowledge compile",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    import webbrowser

    if not webbrowser.open(html_path.resolve().as_uri()):
        typer.secho("open: browser launch failed", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.echo(str(html_path))


@app.command()
def serve(
    port: Annotated[int, typer.Option()] = 8765,
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Serve a bounded local-only read-only knowledge server."""

    root = repository_root.resolve()
    html_path = root / ".knowledge/exports/repo-wiki.html"
    if not html_path.is_file():
        typer.secho(
            "serve: compiled HTML Wiki not found; run knowledge compile",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    from knowledge_compiler.serving import ServeError, create_wiki_server

    try:
        server = create_wiki_server(root, port=port)
    except (ServeError, OSError) as error:
        typer.secho(f"serve: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    typer.echo(
        f"serve: read-only Wiki on http://{server.server_address[0]}:"
        f"{server.server_address[1]}/repo-wiki.html (Ctrl+C to stop)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        typer.echo("serve: stopped")
    finally:
        server.server_close()


@app.command()
def edit(
    object_id: Annotated[str, typer.Argument()],
    print_path: Annotated[bool, typer.Option("--print-path")] = False,
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Create or open the object's human overlay for editing."""

    import os
    import subprocess

    object_type = object_id.split(".", 1)[0]
    if object_type not in ("module", "architecture", "flow", "rule", "tech-stack"):
        typer.secho(
            f"unknown knowledge type in object id: {object_id}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    _type_directories = {
        "module": "modules",
        "architecture": "architecture",
        "flow": "flows",
        "rule": "rules",
        "tech-stack": "tech-stack",
    }
    overlay_dir = (
        repository_root / ".knowledge/human" / _type_directories[object_type]
    )
    overlay_path = overlay_dir / f"{object_id}.yaml"

    if print_path:
        typer.echo(str(overlay_path))
        return

    overlay_dir.mkdir(parents=True, exist_ok=True)
    if not overlay_path.exists():
        import datetime as _datetime

        import yaml as _yaml

        template = {
            "schema_version": "0.1",
            "object_id": object_id,
            "updated_at": _datetime.datetime.now(
                _datetime.timezone.utc
            ).isoformat(),
            "sections": [],
            "notes": [],
        }
        overlay_path.write_text(
            _yaml.safe_dump(template, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    editor = os.environ.get("EDITOR", "vi")
    try:
        result = subprocess.run([editor, str(overlay_path)], check=False)
        if result.returncode != 0:
            typer.secho(f"editor exited {result.returncode}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    except FileNotFoundError:
        typer.secho(f"editor not found: {editor}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    from knowledge_compiler.contracts.human import HumanOverlay

    import yaml as _yaml_validate

    try:
        payload = _yaml_validate.safe_load(
            overlay_path.read_text(encoding="utf-8")
        )
        HumanOverlay.model_validate(payload)
    except (OSError, ValueError, Exception) as error:
        typer.secho(
            f"overlay validation failed (file kept for correction): {error}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from None

    typer.echo(f"overlay valid: {overlay_path}")


@app.command()
def update(
    executor: Annotated[str, typer.Option()] = "llm",
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Incremental update: detect changes, invalidate, retry, retire."""

    if executor not in {"llm", "agent"}:
        typer.secho(
            f"update: unsupported executor {executor!r}; expected llm or agent",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    root = repository_root.resolve()
    config_path = root / ".knowledge/config.yaml"
    from knowledge_compiler.preflight import PreflightFailure, run_preflight

    try:
        run_preflight(root, config_path=config_path)
    except PreflightFailure as error:
        typer.secho(f"preflight: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    import json as _json
    try:
        from knowledge_compiler.incremental.updating import run_incremental_update

        outcome = run_incremental_update(
            repository_root=root,
            executor=executor,
            config=load_config(config_path),
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(f"update: {_short(str(error))}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    change_set = outcome.change_set
    typer.echo(
        f"update: change_set added={len(change_set.added)} "
        f"modified={len(change_set.modified)} deleted={len(change_set.deleted)} "
        f"renamed={len(change_set.renamed)}"
    )
    typer.echo(f"update: pending_targets={len(outcome.pending_target_ids)}")

    report_path = root / ".knowledge/state/last-update.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _json.dumps(
            {
                "status": outcome.status,
                "full_refresh": outcome.full_refresh,
                "refresh_reason": outcome.refresh_reason,
                "invalidation_generation": outcome.invalidation_generation,
                "stale_object_ids": list(outcome.stale_object_ids),
                "retired_object_ids": list(outcome.retired_object_ids),
                "pending_target_ids": list(outcome.pending_target_ids),
                "generation": outcome.generation,
                "published_object_ids": list(outcome.published_object_ids),
                "diagnostics": list(outcome.diagnostics),
                "change_set": {
                    "added": list(change_set.added),
                    "modified": list(change_set.modified),
                    "deleted": list(change_set.deleted),
                    "renamed": [list(pair) for pair in change_set.renamed],
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    typer.echo(f"update: {outcome.status}")
    if outcome.status == "complete":
        return
    raise typer.Exit(code=2 if outcome.status == "partial" else 1)


@app.command()
def validate(
    repository_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Validate the canonical store consistency (exit 0/1)."""

    import yaml

    root = repository_root.resolve()
    knowledge = root / ".knowledge"
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
    if not isinstance(manifest, dict):
        typer.secho("validate: manifest is invalid", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    active = manifest.get("active_generation")
    agent_views = manifest.get("agent_views_generation")
    if not isinstance(active, str) or agent_views != active:
        values = {
            "active_generation": active,
            "agent_views_generation": agent_views,
        }
        typer.secho(
            "validate: generation markers disagree: " + json_dumps(values),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    inventory = manifest.get("objects")
    if not isinstance(inventory, list) or not inventory:
        typer.secho(
            "validate: manifest object inventory is unavailable",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    type_directories = {
        "module": "modules",
        "architecture": "architecture",
        "flow": "flows",
        "rule": "rules",
        "tech-stack": "tech-stack",
    }
    expected_files = []
    for item in inventory:
        if not isinstance(item, dict):
            typer.secho(
                "validate: manifest object inventory is invalid",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        object_id = item.get("id")
        object_type = item.get("type")
        directory = type_directories.get(object_type)
        if not isinstance(object_id, str) or directory is None:
            typer.secho(
                "validate: manifest object inventory is invalid",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        expected_files.extend(
            [
                knowledge / f"objects/{directory}/{object_id}.yaml",
                knowledge / f"views/cards/{object_id}.md",
                knowledge / f"views/wiki/{directory}/{object_id}.md",
            ]
        )
    missing = [str(path) for path in expected_files if not path.is_file()]
    if missing:
        typer.secho(
            "validate: missing published files: " + ", ".join(missing),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    typer.echo(f"validate: generation {active} consistent")


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
