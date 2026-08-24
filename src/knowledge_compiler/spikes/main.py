from __future__ import annotations

from pathlib import Path

import typer

from knowledge_compiler.spikes.cli_probe import run_cli_probe
from knowledge_compiler.spikes.evaluator import SpikeDecision, evaluate
from knowledge_compiler.spikes.fixture_repo import materialize_probe_repo
from knowledge_compiler.spikes.mcp_probe import run_mcp_probe
from knowledge_compiler.spikes.observations import ProbeBundle, write_bundle


app = typer.Typer(no_args_is_help=True)


MCP_CAPABILITY_MAP = {
    "repository_survey": "survey",
    "symbols": "symbols",
    "imports": "topic_exploration",
    "calls": "topic_exploration",
    "source_references": "source_references",
    "topic_exploration": "topic_exploration",
    "affected": "affected",
}


def render_report(bundle: ProbeBundle, decision: SpikeDecision) -> str:
    lines = [
        "# CodeWiki Public-Surface Spike",
        "",
        f"- CodeWiki version: `{bundle.codewiki_version or 'unavailable'}`",
        f"- Probe repository commit: `{bundle.repository_commit}`",
        f"- Decision: `{decision.decision}`",
        "",
        "## CLI observations",
        "",
        "| Command | Exit | Machine-readable JSON |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| `{item.name}` | {item.returncode} | {'yes' if item.json_value is not None else 'no'} |"
        for item in bundle.commands
    )
    lines.extend([
        "",
        "## MCP fallback observations",
        "",
    ])
    if bundle.mcp:
        lines.extend([
            "| Capability | Tool | Error | Structured content |",
            "|---|---|---|---|",
        ])
        lines.extend(
            f"| `{item.name}` | `{item.tool_name or '-'}` | "
            f"{'yes' if item.is_error else 'no'} | "
            f"{'yes' if item.structured_content is not None else 'no'} |"
            for item in bundle.mcp
        )
    else:
        lines.append("MCP fallback was not required.")
    lines.extend([
        "",
        "## Capability matrix",
        "",
        "| Capability | Status | Evidence |",
        "|---|---|---|",
    ])
    lines.extend(
        f"| `{item.capability}` | `{item.status}` | {', '.join(f'`{ref}`' for ref in item.evidence)} |"
        for item in decision.capabilities
    )
    lines.extend([
        "",
        "## Missing or ambiguous capabilities",
        "",
    ])
    if decision.missing_capabilities:
        lines.extend(f"- `{name}`" for name in decision.missing_capabilities)
    else:
        lines.append("None.")
    lines.extend([
        "",
        "## Adapter recommendation",
        "",
    ])
    if decision.decision == "go":
        lines.append(
            "Proceed to the Fake Provider vertical slice using only the captured public-surface contract."
        )
    else:
        lines.append(
            "Stop CodeWiki-based product implementation and revise the design around the missing public capabilities. "
            "Do not import provider internals or read its database."
        )
    return "\n".join(lines) + "\n"


def execute_spike(
    repo_template: Path,
    work_dir: Path,
    report: Path,
    executable: str = "codewiki",
) -> SpikeDecision:
    probe_root = work_dir / "probe-repository"
    repo = materialize_probe_repo(repo_template, probe_root)
    commands = run_cli_probe(executable, repo)
    version = next((item.stdout.strip() for item in commands if item.name == "version"), None) or None
    bundle = ProbeBundle(
        codewiki_version=version,
        repository_commit=repo.commit,
        commands=commands,
    )
    preliminary = evaluate(bundle)
    required_mcp = {
        MCP_CAPABILITY_MAP[name]
        for name in preliminary.missing_capabilities
        if name in MCP_CAPABILITY_MAP
    }
    if required_mcp:
        bundle.mcp = run_mcp_probe(executable, repo, required_mcp)
    decision = evaluate(bundle)
    write_bundle(bundle, work_dir / "probe-bundle.json")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(bundle, decision), encoding="utf-8")
    return decision


@app.command("run")
def run_command(
    repo_template: Path = typer.Option(..., exists=True, file_okay=False),
    work_dir: Path = typer.Option(...),
    report: Path = typer.Option(...),
    executable: str = typer.Option("codewiki"),
) -> None:
    try:
        decision = execute_spike(repo_template, work_dir, report, executable)
    except Exception as exc:
        typer.echo(f"probe infrastructure failure: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Decision: {decision.decision}")
    raise typer.Exit(0 if decision.decision == "go" else 2)


if __name__ == "__main__":
    app()
