from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from knowledge_compiler.cli import app


Runner = CliRunner()


def test_edit_print_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(
        app, ["edit", "module.shop.checkout", "--print-path"]
    )
    assert result.exit_code == 0
    assert "module.shop.checkout.yaml" in result.output


def test_edit_rejects_unknown_object_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(app, ["edit", "hologram.shop.thing", "--print-path"])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_edit_prints_flows_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = Runner.invoke(app, ["edit", "flow.shop.checkout", "--print-path"])
    assert result.exit_code == 0
    assert "flows" in result.output
