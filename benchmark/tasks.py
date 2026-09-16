"""Task manifest loading and validation for the M8 A/B benchmark.

Manifests are plain YAML so they can be reviewed and frozen before a
run. Validation is strict: a malformed manifest must fail before any
agent or repository work happens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_SCHEMA_VERSION = "0.1"
_DIFFICULTIES = ("simple", "medium")
_REPO_PATTERN = re.compile(r"^[\w./:-]+$")


class ManifestError(ValueError):
    """Raised when a task manifest violates the frozen schema."""


@dataclass(frozen=True)
class Task:
    task_id: str
    repo: str
    repo_path: str | None
    base_commit: str | None
    difficulty: str
    prompt: str
    test_cmd: tuple[str, ...]
    fail_to_pass: tuple[str, ...]
    token_cap: int = 60000

    def is_local(self) -> bool:
        return self.repo == "local"


@dataclass(frozen=True)
class Manifest:
    path: Path
    tasks: tuple[Task, ...] = field(default=())

    @property
    def repositories(self) -> tuple[str, ...]:
        seen: list[str] = []
        for task in self.tasks:
            key = task.repo_path if task.is_local() else task.repo
            if key not in seen:
                seen.append(key)
        return tuple(seen)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def load_manifest(path: str | Path) -> Manifest:
    file = Path(path)
    _require(file.is_file(), f"manifest not found: {file}")
    payload = yaml.safe_load(file.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), "manifest must be a mapping")
    _require(
        payload.get("schema_version") == _SCHEMA_VERSION,
        f"schema_version must be '{_SCHEMA_VERSION}'",
    )
    entries = payload.get("tasks")
    _require(isinstance(entries, list) and entries, "tasks must be a non-empty list")

    tasks: list[Task] = []
    seen_ids: set[str] = set()
    for position, entry in enumerate(entries):
        _require(isinstance(entry, dict), f"task #{position} must be a mapping")
        task_id = entry.get("task_id")
        _require(
            isinstance(task_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", task_id or ""),
            f"task #{position}: task_id must be kebab-case",
        )
        _require(task_id not in seen_ids, f"duplicate task_id: {task_id}")
        seen_ids.add(task_id)

        repo = entry.get("repo")
        _require(isinstance(repo, str) and repo, f"{task_id}: repo is required")
        repo_path = entry.get("repo_path")
        if repo == "local":
            _require(
                isinstance(repo_path, str) and repo_path,
                f"{task_id}: local tasks need repo_path",
            )
        else:
            _require(
                isinstance(repo, str)
                and (repo.startswith("https://") or _REPO_PATTERN.match(repo)),
                f"{task_id}: repo must be 'local' or an https URL",
            )
            _require(repo_path is None, f"{task_id}: repo_path only applies to local")

        difficulty = entry.get("difficulty")
        _require(
            difficulty in _DIFFICULTIES,
            f"{task_id}: difficulty must be one of {_DIFFICULTIES}",
        )
        prompt = entry.get("prompt")
        _require(
            isinstance(prompt, str) and len(prompt.strip()) >= 20,
            f"{task_id}: prompt must be a substantive instruction",
        )
        test_cmd = entry.get("test_cmd")
        _require(
            isinstance(test_cmd, list)
            and test_cmd
            and all(isinstance(part, str) and part for part in test_cmd),
            f"{task_id}: test_cmd must be a non-empty argv list",
        )
        fail_to_pass = entry.get("fail_to_pass")
        _require(
            isinstance(fail_to_pass, list)
            and fail_to_pass
            and all(isinstance(item, str) and item for item in fail_to_pass),
            f"{task_id}: fail_to_pass must list at least one test id",
        )
        token_cap = entry.get("token_cap", 60000)
        _require(
            isinstance(token_cap, int) and 1000 <= token_cap <= 400000,
            f"{task_id}: token_cap must be 1000-400000",
        )
        base_commit = entry.get("base_commit")
        _require(
            base_commit is None or isinstance(base_commit, str),
            f"{task_id}: base_commit must be a string or null",
        )

        tasks.append(
            Task(
                task_id=task_id,
                repo=repo,
                repo_path=repo_path,
                base_commit=base_commit,
                difficulty=difficulty,
                prompt=prompt,
                test_cmd=tuple(test_cmd),
                fail_to_pass=tuple(fail_to_pass),
                token_cap=token_cap,
            )
        )

    _require(len(tasks) >= 2, "a manifest needs at least two tasks")
    return Manifest(path=file, tasks=tuple(tasks))


__all__ = ["Manifest", "ManifestError", "Task", "load_manifest"]
