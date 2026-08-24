from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class ProbeRepository:
    root: Path
    commit: str
    eligible_files: tuple[str, ...]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def materialize_probe_repo(template: Path, destination: Path) -> ProbeRepository:
    destination = destination.resolve()
    shutil.copytree(template, destination)
    _git(destination, "init", "-q")
    _git(destination, "config", "user.name", "Knowledge Compiler Spike")
    _git(destination, "config", "user.email", "spike@example.invalid")
    _git(destination, "add", ".")
    _git(destination, "commit", "-q", "-m", "fixture: initial repository")
    files = tuple(
        line
        for line in _git(destination, "ls-files").splitlines()
        if line and not line.startswith((".knowledge/", ".codewiki/"))
    )
    return ProbeRepository(
        root=destination,
        commit=_git(destination, "rev-parse", "HEAD"),
        eligible_files=files,
    )
