from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from knowledge_compiler.cli import app


Runner = CliRunner()


def test_primary_view_commands_use_the_design_names() -> None:
    result = Runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "compile" in result.output
    assert "context" in result.output
    assert "open" in result.output
    assert "compile-views" not in result.output
    assert "knowledge-context" not in result.output
    assert "open-wiki" not in result.output


def test_compile_fails_closed_without_a_committed_generation(
    tmp_path: Path,
) -> None:
    result = Runner.invoke(
        app,
        ["compile", "--repository-root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "no committed generation" in result.output


def test_context_fails_closed_without_safe_agent_views(tmp_path: Path) -> None:
    result = Runner.invoke(
        app,
        [
            "context",
            "trace checkout",
            "--repository-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "knowledge_update_required" in result.output


def test_open_fails_closed_without_compiled_html(tmp_path: Path) -> None:
    result = Runner.invoke(
        app,
        ["open", "--repository-root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "HTML Wiki" in result.output


def test_serve_fails_closed_without_compiled_html(tmp_path: Path) -> None:
    result = Runner.invoke(
        app,
        ["serve", "--repository-root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "HTML Wiki" in result.output
