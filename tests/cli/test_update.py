from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from knowledge_compiler.cli import app


ROOT = Path(__file__).resolve().parents[1]
Runner = CliRunner()


def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    (repo / "core.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


def test_update_first_run_creates_baseline(tmp_path: Path, monkeypatch) -> None:
    repo = git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(app, ["update", "--repository-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "added=1" in result.output
    baseline = repo / ".knowledge/baseline/eligible-files.json"
    assert baseline.is_file()
    report = repo / ".knowledge/state/last-update.json"
    assert report.is_file()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["full_refresh"] is True
    assert payload["refresh_reason"] == "baseline_missing"


def test_update_corrupt_baseline_triggers_full_refresh(
    tmp_path: Path, monkeypatch
) -> None:
    repo = git_repo(tmp_path)
    baseline = repo / ".knowledge/baseline/eligible-files.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("{broken", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = Runner.invoke(app, ["update", "--repository-root", str(repo)])

    assert result.exit_code == 0, result.output
    assert "added=1" in result.output
    payload = json.loads(
        (repo / ".knowledge/state/last-update.json").read_text(encoding="utf-8")
    )
    assert payload["full_refresh"] is True
    assert payload["refresh_reason"] == "baseline_corrupt"


def test_update_detects_modification(tmp_path: Path, monkeypatch) -> None:
    repo = git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    first = Runner.invoke(app, ["update", "--repository-root", str(repo)])
    assert first.exit_code == 0

    (repo / "core.py").write_text("x = 42\n", encoding="utf-8")
    second = Runner.invoke(app, ["update", "--repository-root", str(repo)])
    assert second.exit_code == 0
    assert "modified=1" in second.output


def test_update_no_diff_is_noop(tmp_path: Path, monkeypatch) -> None:
    repo = git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    first = Runner.invoke(app, ["update", "--repository-root", str(repo)])
    second = Runner.invoke(app, ["update", "--repository-root", str(repo)])
    assert "modified=0" in second.output
    assert "added=0" in second.output
    assert "deleted=0" in second.output


def test_update_fails_cleanly_on_plain_dir(tmp_path: Path, monkeypatch) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(app, ["update", "--repository-root", str(plain)])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
