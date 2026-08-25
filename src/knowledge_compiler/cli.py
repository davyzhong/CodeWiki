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
    outcome = _run_orchestrated_build(repository_root.resolve())
    if outcome is None:
        typer.secho(
            "build: the repository needs a Git-initialized eligible target; "
            "run knowledge init and commit source first",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    status, generation, published = outcome
    report_path = Path(".knowledge/state/runs") / "last-build.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json

    report_path.write_text(
        _json.dumps(
            {
                "status": status,
                "generation": generation,
                "published_object_ids": list(published),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    typer.echo(f"build: {status} generation={generation}")
    if status == "complete":
        return
    raise typer.Exit(code=2 if status == "partial" else 1)


def _run_orchestrated_build(repository_root: Path):
    """Drive the orchestrator over the repository when possible."""

    import shutil
    import tempfile

    from knowledge_compiler.contracts.repository import (
        EvidenceBudget,
        PlanTarget,
    )
    from knowledge_compiler.orchestrator.contracts import RunRecord
    from knowledge_compiler.orchestrator.queue import RunQueue
    from knowledge_compiler.orchestrator.runner import RunOrchestrator
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
        RepositoryResolutionError,
    )

    class _WallClock:
        def __call__(self) -> int:
            import time

            return int(time.time())

    try:
        LocalGitRepositoryProvider().resolve(repository_root)
    except RepositoryResolutionError:
        return None
    from knowledge_compiler.providers.fake import FakeEvidenceProvider

    fixtures = (
        Path(__file__).resolve().parents[2] / "tests/fixtures/fake_provider"
    ).resolve()
    if not fixtures.is_dir():
        return None  # fixture world unavailable in this checkout
    # Fixture mode: the build drives the orchestrated pipeline when the
    # repository is the probe fixture world; real-repository builds need the
    # live CodeWiki adapter + LiteLLM worker (environment-driven, M4.8b).
    try:
        provider = FakeEvidenceProvider(
            fixture_dir=fixtures, repository_root=repository_root
        )
    except ValueError:
        return None
    # The fixture world owns its frozen snapshot identity; the resolved
    # git repo only proves the repository is real and has a commit.
    snapshot = provider.bound_repository()
    run_record = RunRecord.model_validate(
        {
            "run_id": "cli-build-001",
            "repository_id": snapshot.repository_id,
            "snapshot_id": snapshot.snapshot_id,
            "executor": "llm",
            "active": True,
            "targets": (
                {
                    "target_id": "module.shop.checkout",
                    "object_type": "module",
                    "state": "queued",
                    "attempt": 1,
                    "repair_attempts": 0,
                    "required": True,
                    "priority": 1,
                    "result": None,
                    "published_object_id": None,
                    "request_digest": "sha256:" + "0" * 64,
                    "result_digest": None,
                    "diagnostics": (),
                    "lease": None,
                },
            ),
        }
    )
    queue = RunQueue(
        store_root=Path(".knowledge/state/runs"),
        run=run_record,
        clock=_WallClock(),
    )

    from knowledge_compiler.orchestrator.fixture_worker import FixtureWorker

    orchestrator = RunOrchestrator(
        queue=queue,
        snapshot=snapshot,
        evidence_provider=provider,
        worker=FixtureWorker(),
        output_root=repository_root,
        run_id="cli-build-001",
    )
    outcome = orchestrator.run()
    return outcome.status, outcome.generation, outcome.published_object_ids


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

    from knowledge_compiler.preflight import PreflightFailure, run_preflight

    try:
        run_preflight(repository_root.resolve())
    except PreflightFailure as error:
        typer.secho(f"preflight: {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    import json as _json
    from knowledge_compiler.repository.changes import compute_changes
    from knowledge_compiler.repository.inventory import (
        FileRecord,
        load_baseline,
        save_baseline,
    )
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
    )

    baseline_path = repository_root / ".knowledge/baseline/eligible-files.json"
    provider = LocalGitRepositoryProvider()
    current = tuple(
        FileRecord(
            path=r.path,
            blob_id=r.blob_id,
            content_hash=r.content_hash,
            size=r.size,
            language=r.language,
        )
        for r in provider.inventory(repository_root.resolve())
    )
    if baseline_path.exists():
        try:
            baseline = load_baseline(baseline_path)
        except ValueError:
            baseline = current
    else:
        baseline = current

    change_set = compute_changes(baseline, current)
    typer.echo(
        f"update: change_set added={len(change_set.added)} "
        f"modified={len(change_set.modified)} deleted={len(change_set.deleted)} "
        f"renamed={len(change_set.renamed)}"
    )
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    save_baseline(baseline_path, current)

    pending_path = repository_root / ".knowledge/state/pending-targets.json"
    if pending_path.exists():
        from knowledge_compiler.incremental.pending import PendingStore

        pending = PendingStore(pending_path)
        typer.echo(f"update: pending_targets={len(pending.target_ids())}")

    report_path = repository_root / ".knowledge/state/last-update.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _json.dumps(
            {
                "status": "complete",
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
    typer.echo("update: complete")


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
