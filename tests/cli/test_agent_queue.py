from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knowledge_compiler.cli import app
from knowledge_compiler.orchestrator.contracts import TargetState


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/orchestrator"))

Runner = CliRunner()


def knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / ".knowledge"
    root.mkdir(exist_ok=True)
    return root


def test_agent_commands_hidden_from_primary_help(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    knowledge_root(tmp_path)
    result = Runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("prepare", "next", "evidence", "finalize"):
        assert command not in result.output.lower() or "queue" in result.output.lower()


def test_prepare_creates_active_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(
        app,
        [
            "prepare",
            "--repository-root", str(tmp_path),
            "--repository-id", "fixture/probe-shop",
            "--snapshot-id", "sha256:" + "2" * 64,
            "--target", "module.shop.checkout",
        ],
    )
    assert result.exit_code == 0, result.output
    runs = tmp_path / ".knowledge/state/runs"
    assert any(run.is_dir() for run in runs.iterdir())
    payload = json.loads(
        next(runs.iterdir()).joinpath("run.json").read_text(encoding="utf-8")
    )
    assert payload["executor"] == "agent"
    assert payload["active"] is True


def test_prepare_rejects_second_active_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    common = [
        "--repository-root", str(tmp_path),
        "--repository-id", "fixture/probe-shop",
        "--snapshot-id", "sha256:" + "2" * 64,
        "--target", "module.shop.checkout",
    ]
    first = Runner.invoke(app, ["prepare", *common])
    assert first.exit_code == 0
    second = Runner.invoke(app, ["prepare", *common])
    assert second.exit_code == 1
    assert "active" in second.output
    assert second.exception is None or isinstance(second.exception, SystemExit)


def test_next_fails_closed_when_manual_queue_has_no_evidence_pack(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    common = [
        "--repository-root", str(tmp_path),
        "--repository-id", "fixture/probe-shop",
        "--snapshot-id", "sha256:" + "2" * 64,
        "--target", "module.shop.checkout",
    ]
    Runner.invoke(app, ["prepare", *common])
    result = Runner.invoke(app, ["next", "--operation", "extraction"])
    assert result.exit_code == 1
    assert "evidence" in result.output.lower()


def test_verify_next_serves_fresh_context_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    common = [
        "--repository-root", str(tmp_path),
        "--repository-id", "fixture/probe-shop",
        "--snapshot-id", "sha256:" + "2" * 64,
        "--target", "module.shop.checkout",
    ]
    Runner.invoke(app, ["prepare", *common])
    result = Runner.invoke(app, ["verify-next"])
    assert result.exit_code == 1
    assert "semantic_pending" in result.output or "state" in result.output


def test_finalize_and_unknown_commands_fail_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    knowledge_root(tmp_path)
    result = Runner.invoke(app, ["finalize"])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output

    evidence = Runner.invoke(app, ["evidence", "module.shop.ghost"])
    assert evidence.exit_code == 1


def test_prepare_state_is_scoped_to_repository_root(
    tmp_path: Path, monkeypatch
) -> None:
    repository_root = tmp_path / "repo"
    invocation_root = tmp_path / "invocation"
    repository_root.mkdir()
    invocation_root.mkdir()
    monkeypatch.chdir(invocation_root)

    result = Runner.invoke(
        app,
        [
            "prepare",
            "--repository-root", str(repository_root),
            "--repository-id", "fixture/probe-shop",
            "--snapshot-id", "sha256:" + "2" * 64,
            "--target", "module.shop.checkout",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (repository_root / ".knowledge/state/runs").is_dir()
    assert not (invocation_root / ".knowledge").exists()
