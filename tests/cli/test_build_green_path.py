from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knowledge_compiler.cli import app


ROOT = Path(__file__).resolve().parents[1]
Runner = CliRunner()


def git_repo_with_fixture_content(tmp_path: Path) -> Path:
    """A real git repo whose content IS the probe fixture world."""

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    import shutil

    source = ROOT / "fixtures/probe_repo"
    for item in source.iterdir():
        if item.is_dir():
            shutil.copytree(item, repo / item.name)
        else:
            shutil.copy(item, repo / item.name)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    return repo


def test_build_green_path_publishes_generation(tmp_path: Path, monkeypatch) -> None:
    repo = git_repo_with_fixture_content(tmp_path)
    monkeypatch.chdir(repo)
    result = Runner.invoke(app, ["build", "--executor", "llm", "--repository-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "complete" in result.output
    manifest = repo / ".knowledge/manifest.yaml"
    assert manifest.is_file()
    report = repo / ".knowledge/state/runs/last-build.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert "module.shop.checkout" in payload["published_object_ids"]


def test_build_state_is_scoped_to_repository_root(
    tmp_path: Path, monkeypatch
) -> None:
    repo = git_repo_with_fixture_content(tmp_path)
    invocation_root = tmp_path / "invocation"
    invocation_root.mkdir()
    monkeypatch.chdir(invocation_root)

    result = Runner.invoke(
        app,
        ["build", "--executor", "llm", "--repository-root", str(repo)],
    )

    assert result.exit_code == 0, result.output
    assert (repo / ".knowledge/state/runs/last-build.json").is_file()
    assert not (invocation_root / ".knowledge").exists()


def test_build_fails_cleanly_on_plain_repository(tmp_path: Path, monkeypatch) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(plain)], check=True)
    subprocess.run(["git", "-C", str(plain), "config", "user.email", "t@e.com"], check=True)
    subprocess.run(["git", "-C", str(plain), "config", "user.name", "T"], check=True)
    (plain / "core.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(plain), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(plain), "commit", "-qm", "init"], check=True)
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(app, ["build", "--executor", "llm", "--repository-root", str(plain)])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output


def test_agent_protocol_full_walk(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    common = [
        "--repository-root", str(ROOT / "fixtures/probe_repo"),
        "--repository-id", "fixture/probe-shop",
        "--snapshot-id", "sha256:" + "2" * 64,
        "--target", "module.shop.checkout",
    ]
    assert Runner.invoke(app, ["prepare", *common]).exit_code == 0

    next_result = Runner.invoke(app, ["next", "--operation", "extraction"])
    assert next_result.exit_code == 0
    lease = json.loads(next_result.output)["lease"]["token"]

    draft = tmp_path / "draft.json"
    draft.write_text('{"draft": "fixture"}', encoding="utf-8")
    submitted = Runner.invoke(
        app, ["submit-extraction", str(draft), "--lease", lease]
    )
    assert submitted.exit_code == 0, submitted.output
    assert "semantic_pending" in submitted.output

    verify = Runner.invoke(app, ["verify-next"])
    assert verify.exit_code == 0, verify.output

    verify_lease_result = Runner.invoke(
        app, ["next", "--operation", "verification"]
    )
    assert verify_lease_result.exit_code == 0, verify_lease_result.output
    verify_lease = json.loads(verify_lease_result.output)["lease"]["token"]

    result_file = tmp_path / "result.json"
    result_file.write_text('{"verifications": []}', encoding="utf-8")
    wrong_lease = Runner.invoke(
        app,
        ["submit-verification", str(result_file), "--lease", "wrong-token"],
    )
    assert wrong_lease.exit_code == 1

    good = Runner.invoke(
        app,
        ["submit-verification", str(result_file), "--lease", verify_lease],
    )
    assert good.exit_code == 0, good.output
    assert "verified" in good.output

    finalize = Runner.invoke(app, ["finalize"])
    assert finalize.exit_code == 0


def test_submit_verification_rejects_expired_or_wrong_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    common = [
        "--repository-root", str(ROOT / "fixtures/probe_repo"),
        "--repository-id", "fixture/probe-shop",
        "--snapshot-id", "sha256:" + "2" * 64,
        "--target", "module.shop.checkout",
    ]
    Runner.invoke(app, ["prepare", *common])
    result_file = tmp_path / "r.json"
    result_file.write_text("{}", encoding="utf-8")
    # No verification lease granted yet -> submission must fail.
    rejected = Runner.invoke(
        app, ["submit-verification", str(result_file), "--lease", "any"]
    )
    assert rejected.exit_code == 1
