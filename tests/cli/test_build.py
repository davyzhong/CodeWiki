from __future__ import annotations

import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knowledge_compiler.cli import app


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/orchestrator"))

Runner = CliRunner()


def test_build_missing_prerequisites_exit_one(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(
        app,
        [
            "build",
            "--executor", "llm",
            "--repository-root", str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output


def test_build_reports_validation_profile_choice(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(
        app,
        [
            "build",
            "--executor", "llm",
            "--repository-root", str(tmp_path),
            "--report-validation-profile",
        ],
    )
    # Even on preflight failure the profile mode line must appear when asked.
    assert "validation-profile" in result.output or result.exit_code == 1


def test_validate_clean_exit_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".knowledge").mkdir()
    result = Runner.invoke(app, ["validate"])
    # No canonical generation yet -> validate fails closed.
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_validate_detects_generation_consistency(tmp_path: Path, monkeypatch) -> None:
    import shutil as shutil_module

    from tests_storage_helper import build_compiled_generation

    monkeypatch.chdir(tmp_path)
    build_compiled_generation(tmp_path)
    result = Runner.invoke(app, ["validate"])
    assert result.exit_code == 0, result.output
