"""M8 A/B benchmark runner (CLI).

Standard library only. See benchmark/README.md for usage; the frozen
design lives in docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backends import make_backend  # noqa: E402
from scoring import (  # noqa: E402
    append_jsonl,
    make_record,
    read_jsonl,
)
from stats import render_summary_markdown, summarize  # noqa: E402
from tasks import load_manifest  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]

_DRYRUN_CONTEXT = """# Dry-run knowledge context (synthetic)

This placeholder stands in for `knowledge context "<task>"` output so
the dry-run pipeline exercises the injection path without a live
knowledge build.
"""


def _prepare_workspace(task, workspace_root: Path) -> Path:
    if task.is_local():
        source = _ROOT / task.repo_path
        if not source.is_dir():
            raise FileNotFoundError(f"local repo_path missing: {source}")
        workspace = workspace_root / task.task_id
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(source, workspace)
    else:
        workspace = workspace_root / task.task_id
        if not workspace.exists():
            subprocess.run(
                ["git", "clone", task.repo, str(workspace)],
                check=True,
                capture_output=True,
                timeout=600,
            )
    if task.base_commit:
        subprocess.run(
            ["git", "-C", str(workspace), "checkout", task.base_commit],
            check=True,
            capture_output=True,
        )
    return workspace


def _build_knowledge(workspace: Path) -> None:
    knowledge_cli = _ROOT / ".venv/bin/knowledge"
    subprocess.run(
        [str(knowledge_cli), "init", "--language", "en"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(knowledge_cli), "build", "--executor", "llm"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(knowledge_cli), "compile"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )


def _treatment_context(workspace: Path, task) -> str:
    knowledge_cli = _ROOT / ".venv/bin/knowledge"
    completed = subprocess.run(
        [str(knowledge_cli), "context", task.prompt[:200]],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"knowledge context failed: {completed.stderr[:300]}"
        )
    return completed.stdout


def cmd_run(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    backend = make_backend(args.backend)
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    if not seeds:
        print("seeds must be a comma-separated list", file=sys.stderr)
        return 2
    results_root = Path(args.results).resolve()
    stamp = _datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = results_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = run_dir / "runs.jsonl"

    for task in manifest.tasks:
        workspace = _prepare_workspace(task, run_dir)
        context_markdown: str | None = None
        if args.knowledge == "build":
            _build_knowledge(workspace)
            context_markdown = _treatment_context(workspace, task)
        elif args.knowledge == "existing":
            context_markdown = _treatment_context(workspace, task)
        elif backend.name == "dryrun":
            context_markdown = _DRYRUN_CONTEXT

        for arm in ("control", "treatment-a"):
            for seed in seeds:
                outcome = backend.run(
                    task=task,
                    workspace=workspace,
                    arm=arm,
                    seed=seed,
                    context_markdown=context_markdown
                    if arm == "treatment-a"
                    else None,
                )
                if backend.name == "dryrun":
                    record = make_record(
                        task=task,
                        arm=arm,
                        seed=seed,
                        success=outcome.ran,
                        outcome=outcome,
                        backend_name=backend.name,
                        verdict_source="simulated",
                    )
                else:
                    from scoring import verify_fail_to_pass

                    passed, _tail = verify_fail_to_pass(
                        workspace, task.test_cmd, task.fail_to_pass
                    )
                    record = make_record(
                        task=task,
                        arm=arm,
                        seed=seed,
                        success=passed and outcome.ran,
                        outcome=outcome,
                        backend_name=backend.name,
                        verdict_source="test-command",
                    )
                    subprocess.run(
                        ["git", "-C", str(workspace), "checkout", "--", "."],
                        check=False,
                        capture_output=True,
                    )
                append_jsonl(jsonl_path, record)
                print(
                    f"{task.task_id} {arm} seed={seed}:"
                    f" success={record.success}"
                )
        if not args.keep_workspaces:
            shutil.rmtree(workspace, ignore_errors=True)

    records = read_jsonl(jsonl_path)
    summaries, verdict = summarize(records)
    summary_md = render_summary_markdown(
        manifest.path.name, summaries, verdict
    )
    (run_dir / "summary.md").write_text(summary_md, encoding="utf-8")
    print(summary_md)
    print(f"results: {run_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark-runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="execute a benchmark")
    run_parser.add_argument("--manifest", required=True)
    run_parser.add_argument(
        "--backend", default="dryrun", choices=("dryrun", "claude-code")
    )
    run_parser.add_argument("--seeds", default="1,2,3")
    run_parser.add_argument("--results", default="benchmark/results")
    run_parser.add_argument(
        "--knowledge",
        default="skip",
        choices=("skip", "existing", "build"),
        help="skip: no knowledge; existing: use .knowledge already in the"
        " repo copy; build: full init/build/compile (needs API key)",
    )
    run_parser.add_argument("--keep-workspaces", action="store_true")
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
