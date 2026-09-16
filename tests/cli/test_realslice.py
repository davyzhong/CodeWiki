from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from knowledge_compiler.cli import app


Runner = CliRunner()


def test_realslice_help() -> None:
    # Assert against command metadata, not rendered help: rich's help
    # layout varies with terminal width and library version, while the
    # option set is the actual contract.
    from typer.main import get_command

    result = Runner.invoke(app, ["realslice", "--help"])
    assert result.exit_code == 0
    params = {
        param.name
        for param in get_command(app).commands["realslice"].params
    }
    assert "repository_root" in params
    assert "output_root" in params


def test_realslice_requires_model_configuration(tmp_path: Path, monkeypatch=None) -> None:
    import os

    saved = os.environ.pop("KNOWLEDGE_EXTRACTION_MODEL", None)
    try:
        result = Runner.invoke(
            app,
            [
                "realslice",
                "--repository-root", str(tmp_path),
                "--output-root", str(tmp_path / "out"),
            ],
        )
        assert result.exit_code == 1
        assert result.exception is None or isinstance(result.exception, SystemExit)
        assert "KNOWLEDGE_EXTRACTION_MODEL" in result.output
        assert "Traceback" not in result.output
    finally:
        if saved is not None:
            os.environ["KNOWLEDGE_EXTRACTION_MODEL"] = saved
