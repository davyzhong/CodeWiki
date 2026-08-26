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


def _published_store(tmp_path: Path) -> Path:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tests_storage_helper import build_published_generation

    build_published_generation(tmp_path)
    return tmp_path


def test_compile_publishes_deterministic_views_and_stamps_the_wiki(
    tmp_path: Path,
) -> None:
    import yaml

    _published_store(tmp_path)
    manifest_path = tmp_path / ".knowledge/manifest.yaml"
    before = yaml.safe_load(manifest_path.read_bytes())
    assert before["wiki_generation"] is None

    result = Runner.invoke(
        app,
        ["compile", "--repository-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    assert payload["generation"] == before["active_generation"]
    assert "index.md" in payload["pages"]
    assert "sources.md" in payload["pages"]
    assert payload["html"] == ".knowledge/exports/repo-wiki.html"
    after = yaml.safe_load(manifest_path.read_bytes())
    assert after["wiki_generation"] == after["active_generation"]


def test_open_warns_when_the_wiki_lags_the_active_generation(
    tmp_path: Path, monkeypatch
) -> None:
    _published_store(tmp_path)
    html = tmp_path / ".knowledge/exports/repo-wiki.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<!doctype html><p>older wiki</p>", encoding="utf-8")

    class Browser:
        @staticmethod
        def open(_uri: str) -> bool:
            return True

    monkeypatch.setattr("webbrowser.open", Browser.open)
    result = Runner.invoke(
        app,
        ["open", "--repository-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "lags the active generation" in result.output


def test_open_does_not_warn_when_the_wiki_is_current(
    tmp_path: Path, monkeypatch
) -> None:
    _published_store(tmp_path)
    result = Runner.invoke(
        app,
        ["compile", "--repository-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    class Browser:
        @staticmethod
        def open(_uri: str) -> bool:
            return True

    monkeypatch.setattr("webbrowser.open", Browser.open)
    result = Runner.invoke(
        app,
        ["open", "--repository-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "lags the active generation" not in result.output
