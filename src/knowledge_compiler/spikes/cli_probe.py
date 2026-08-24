from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from knowledge_compiler.spikes.fixture_repo import ProbeRepository
from knowledge_compiler.spikes.observations import CommandObservation, sanitize_text


def _sanitize_value(value: Any, repo_root: Path) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, repo_root)
    if isinstance(value, list):
        return [_sanitize_value(item, repo_root) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_value(item, repo_root) for key, item in value.items()}
    return value


def _run(
    executable: str,
    repo: ProbeRepository,
    name: str,
    args: list[str],
    *,
    stdin: str | None = None,
) -> CommandObservation:
    executable_path = str(Path(executable).resolve()) if "/" in executable else executable
    argv = [executable_path, *args]
    environment = {
        "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PATH": os.environ.get("PATH", ""),
    }
    try:
        result = subprocess.run(
            argv,
            cwd=repo.root,
            env=environment,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        returncode = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except FileNotFoundError as exc:
        returncode, stdout, stderr = 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or "command timed out after 120 seconds"

    try:
        json_value = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        json_value = None

    return CommandObservation(
        name=name,
        argv=[sanitize_text(arg, repo.root) for arg in argv],
        returncode=returncode,
        stdout=sanitize_text(stdout, repo.root),
        stderr=sanitize_text(stderr, repo.root),
        json_value=_sanitize_value(json_value, repo.root),
    )


def run_cli_probe(executable: str, repo: ProbeRepository) -> list[CommandObservation]:
    commands = [
        ("version", ["--version"]),
        ("repos_add", ["repos", "add", str(repo.root), "--json"]),
        ("analyze", ["analyze", str(repo.root), "--json"]),
        ("repos_scan", ["repos", "scan", str(repo.root), "--json"]),
        (
            "graph_search",
            ["graph", "search", "CheckoutService", "--repo", str(repo.root), "--json"],
        ),
        (
            "graph_explore",
            ["graph", "explore", "checkout inventory", "--repo", str(repo.root), "--json"],
        ),
    ]
    observations = [_run(executable, repo, name, args) for name, args in commands]
    observations.append(
        _run(
            executable,
            repo,
            "graph_affected",
            ["graph", "affected", "--repo", str(repo.root), "--stdin", "--json"],
            stdin="src/shop/inventory.py\n",
        )
    )

    inventory = repo.root / "src/shop/inventory.py"
    inventory.write_text(inventory.read_text(encoding="utf-8") + "\n# probe update\n", encoding="utf-8")
    observations.append(_run(executable, repo, "update", ["update", str(repo.root), "--json"]))
    observations.append(
        _run(
            executable,
            repo,
            "graph_search_after_update",
            ["graph", "search", "CheckoutService", "--repo", str(repo.root), "--json"],
        )
    )
    return observations
