from __future__ import annotations

import json
import tomllib
from pathlib import Path

import typer


ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_local_app_runtime_contract_is_packaged() -> None:
    project = _pyproject()["project"]
    dependencies = project["dependencies"]

    for package in ("fastapi", "uvicorn", "platformdirs"):
        matches = [
            dependency
            for dependency in dependencies
            if dependency.lower().startswith(package)
        ]
        assert len(matches) == 1
        assert ">=" in matches[0]
        assert "<" in matches[0]

    assert project["scripts"]["knowledge-app"] == (
        "knowledge_compiler.app.launcher:main"
    )

    from knowledge_compiler.cli import app

    command = typer.main.get_command(app)
    assert "app" in command.commands

    static_index = (
        ROOT / "src/knowledge_compiler/app/static/index.html"
    )
    assert static_index.is_file()
    wheel = _pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert "src/knowledge_compiler" in wheel["packages"]
    assert "src/knowledge_compiler/app/static/**" in wheel["artifacts"]


def test_frontend_toolchain_contract_is_pinned() -> None:
    package = json.loads(
        (ROOT / "web/package.json").read_text(encoding="utf-8")
    )
    assert package["private"] is True
    assert set(package["scripts"]) >= {"test", "build", "typecheck", "e2e"}
    for version in package["devDependencies"].values():
        assert version[0].isdigit(), version

    assert (ROOT / "web/pnpm-lock.yaml").is_file()
    assert (ROOT / "web/tsconfig.json").is_file()
    assert (ROOT / "web/vite.config.ts").is_file()


def test_console_entry_reports_pending_lifecycle_without_traceback(
    capsys,
) -> None:
    from knowledge_compiler.app.launcher import main

    assert main() == 1
    captured = capsys.readouterr()
    assert "not implemented yet" in captured.err
