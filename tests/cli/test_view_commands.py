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


def test_status_reports_target_results_from_the_latest_run(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.orchestrator.contracts import (
        RunRecord,
        TargetRecord,
        TargetState,
        TerminalResult,
    )
    from knowledge_compiler.orchestrator.store import RunStore

    runs = tmp_path / ".knowledge/state/runs"
    RunStore(runs).save(
        RunRecord.model_validate(
            {
                "run_id": "status-run-001",
                "repository_id": "fixture/probe-shop",
                "snapshot_id": "sha256:" + "2" * 64,
                "executor": "llm",
                "active": False,
                "targets": [
                    {
                        "target_id": "module.shop.checkout",
                        "object_type": "module",
                        "attempt": 1,
                        "repair_attempts": 0,
                        "priority": 5,
                        "request_digest": "sha256:" + "1" * 64,
                        "state": "done",
                        "result": "retired",
                    },
                    {
                        "target_id": "flow.order.create",
                        "object_type": "flow",
                        "attempt": 1,
                        "repair_attempts": 0,
                        "priority": 5,
                        "request_digest": "sha256:" + "2" * 64,
                        "state": "done",
                        "result": "conflicted",
                    },
                ],
            }
        )
    )

    result = Runner.invoke(
        app,
        ["status", "--repository-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    assert payload["run_id"] == "status-run-001"
    assert payload["run_active"] is False
    assert payload["target_results"] == [
        {
            "target_id": "flow.order.create",
            "state": "done",
            "result": "conflicted",
            "published_object_id": None,
            "required": True,
        },
        {
            "target_id": "module.shop.checkout",
            "state": "done",
            "result": "retired",
            "published_object_id": None,
            "required": True,
        },
    ]
    del TargetState, TerminalResult


def _published_store(tmp_path: Path) -> Path:
    import subprocess
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tests_storage_helper import build_published_generation

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "shop.py").write_text(
        "def checkout():\n    return 'ok'\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@e.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        [
            "git", "-C", str(tmp_path), "commit", "--allow-empty",
            "-qm", "fixture",
        ],
        check=True,
    )
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
