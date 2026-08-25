from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from knowledge_compiler.config import (
    KnowledgeConfig,
    load_config,
    write_config,
)


def base_payload() -> dict:
    return {
        "schema_version": "0.1",
        "repository_provider": "local-git",
        "evidence_provider": "codewiki",
        "language": "zh",
        "worker_profiles": {
            "extraction_profile": "extraction-v1",
            "validation_profile": None,
        },
        "exclusions": ["docs/"],
        "scope_limits": {"max_files": 10000, "max_bytes": 52428800},
        "default_context_budget": 6000,
    }


def test_config_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    write_config(path, KnowledgeConfig.model_validate(base_payload()))
    loaded = load_config(path)
    assert loaded == KnowledgeConfig.model_validate(base_payload())


def test_config_rejects_unknown_keys(tmp_path: Path) -> None:
    payload = base_payload() | {"surprise": True}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_config(path)


@pytest.mark.parametrize("language", ("fr", "ZH", "", "chinese"))
def test_config_rejects_unsupported_language(language: str) -> None:
    payload = base_payload() | {"language": language}
    with pytest.raises(ValueError):
        KnowledgeConfig.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    ("api_key", "token", "secret", "password", "endpoint", "model_url"),
)
def test_config_rejects_secret_fields(field: str) -> None:
    payload = base_payload() | {field: "x"}
    with pytest.raises(ValueError, match="secret|credential|forbidden"):
        KnowledgeConfig.model_validate(payload)


def test_config_rejects_unsafe_exclusions_and_limits(tmp_path: Path) -> None:
    payload = base_payload() | {"exclusions": ["../escape"]}
    with pytest.raises(ValueError, match="exclusion"):
        KnowledgeConfig.model_validate(payload)
    payload = base_payload() | {"scope_limits": {"max_files": 0}}
    with pytest.raises(ValueError, match="scope"):
        KnowledgeConfig.model_validate(payload)


def test_config_rejects_copied_corruption() -> None:
    config = KnowledgeConfig.model_validate(base_payload())
    corrupted = config.model_copy(update={"language": object()})
    with pytest.raises(ValueError):
        KnowledgeConfig.model_validate(corrupted.model_dump())


def test_init_is_idempotent_and_preserves_user_config(tmp_path: Path) -> None:
    from knowledge_compiler.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    knowledge = tmp_path / ".knowledge"
    knowledge.mkdir()

    first = runner.invoke(app, ["init", "--language", "zh", "--repository-root", str(tmp_path)])
    assert first.exit_code == 0, first.output
    config_path = knowledge / "config.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    payload["exclusions"] = ["legacy/"]
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    second = runner.invoke(app, ["init", "--language", "zh", "--repository-root", str(tmp_path)])
    assert second.exit_code == 0
    assert "legacy/" in yaml.safe_load(config_path.read_text(encoding="utf-8"))["exclusions"]

    conflict = runner.invoke(app, ["init", "--language", "en", "--repository-root", str(tmp_path)])
    assert conflict.exit_code == 1
    assert "Traceback" not in conflict.output


def test_init_writes_gitignore_preserving_user_content(tmp_path: Path) -> None:
    from knowledge_compiler.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# my rules\n*.log\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--language", "en", "--repository-root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    content = gitignore.read_text(encoding="utf-8")
    assert "# my rules" in content
    assert "*.log" in content
    assert ".knowledge/cache" in content
    assert ".knowledge/state" in content
    assert "exports/" in content
    assert ".codewiki/" in content


def test_preflight_stops_in_order_before_any_model_call(tmp_path: Path) -> None:
    import subprocess

    from knowledge_compiler.preflight import PreflightFailure, run_preflight

    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(PreflightFailure, match="Git"):
        run_preflight(plain)

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    with pytest.raises(PreflightFailure, match="commit"):
        run_preflight(repo)

    good = tmp_path / "good"
    good.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(good)], check=True)
    subprocess.run(
        ["git", "-C", str(good), "config", "user.email", "t@e.com"], check=True
    )
    subprocess.run(
        ["git", "-C", str(good), "config", "user.name", "T"], check=True
    )
    (good / "core.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(good), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(good), "commit", "-qm", "init"], check=True
    )

    config = tmp_path / "bad-config.yaml"
    config.write_text("schema_version: '9.9'\n", encoding="utf-8")
    with pytest.raises(PreflightFailure, match="config"):
        run_preflight(good, config_path=config)

    with pytest.raises(PreflightFailure, match="model"):
        run_preflight(good, config_path=None, missing_model_profile=True)


def test_preflight_reports_validation_profile_reuse(tmp_path: Path) -> None:
    from knowledge_compiler.preflight import run_preflight

    result = run_preflight(
        None,
        dry_run=True,
        profiles={"extraction_profile": "extraction-v1", "validation_profile": None},
    )
    assert result["validation_profile_mode"] == "reuses-extraction-profile"
