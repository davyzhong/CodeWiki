"""Agent backends for the M8 A/B benchmark.

A backend receives the task, the arm injection (empty for control), and
the seed; it performs the coding attempt and reports raw usage. The
success verdict is never taken from the backend — `scoring.py` decides
from the repository's own test command.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class BackendOutcome:
    ran: bool
    total_tokens: int
    tool_calls: int
    wall_seconds: float
    final_diff_hash: str | None
    notes: str
    model: str


class AgentBackend(Protocol):
    name: str

    def run(
        self,
        *,
        task: object,
        workspace: Path,
        arm: str,
        seed: int,
        context_markdown: str | None,
    ) -> BackendOutcome: ...


class DryRunBackend:
    """Deterministic synthetic outcomes; nothing under test executes.

    Success is decided by a stable hash of (task, arm, seed) with a
    built-in +2-task treatment bias so the paired statistics exercise
    realistic data shapes. Usage numbers are synthetic and capped at
    the task budget.
    """

    name = "dryrun"

    def run(
        self,
        *,
        task: object,
        workspace: Path,
        arm: str,
        seed: int,
        context_markdown: str | None,
    ) -> BackendOutcome:
        digest = hashlib.sha256(
            f"{task.task_id}|{arm}|{seed}".encode("utf-8")
        ).digest()
        roll = digest[0] / 255.0
        threshold = 0.35 if arm == "treatment-a" else 0.55
        ran = roll >= threshold
        base_tokens = 18000 if arm == "treatment-a" else 26000
        tokens = int(base_tokens * (0.6 + digest[1] / 128.0))
        return BackendOutcome(
            ran=ran,
            total_tokens=min(tokens, task.token_cap),
            tool_calls=8 + digest[2] % 20,
            wall_seconds=30 + digest[3] % 90,
            final_diff_hash=hashlib.sha256(digest).hexdigest()[:16] if ran else None,
            notes="simulated outcome (dryrun backend)",
            model="dryrun-synthetic",
        )


class ClaudeCodeBackend:
    """Headless Claude Code invocation (`claude -p --output-format json`).

    Requires the `claude` CLI on PATH and valid credentials. The token
    cap is communicated in the prompt; the harness records whatever the
    CLI reports. Verdicts still come from the test command.
    """

    name = "claude-code"

    def __init__(self, model: str | None = None) -> None:
        self._model = model

    def run(
        self,
        *,
        task: object,
        workspace: Path,
        arm: str,
        seed: int,
        context_markdown: str | None,
    ) -> BackendOutcome:
        executable = shutil.which("claude")
        if executable is None:
            raise RuntimeError(
                "claude CLI not found on PATH; configure credentials first"
            )
        parts = [
            "You are working on a coding task in the current repository.",
            f"Budget ceiling: {task.token_cap} tokens. Stop and report if exceeded.",
            "",
            "TASK:",
            task.prompt,
        ]
        if context_markdown:
            parts += [
                "",
                "VERIFIED REPOSITORY KNOWLEDGE (pre-extracted, evidence-bound;",
                "treat as background, verify against code before relying on it):",
                "",
                context_markdown,
            ]
        parts += [
            "",
            "Implement the change. Do not modify or commit anything under"
            " .knowledge/. Do not run network calls. Finish with the tests"
            " passing.",
        ]
        argv = [
            executable,
            "-p",
            "\n".join(parts),
            "--output-format",
            "json",
        ]
        if self._model:
            argv += ["--model", self._model]
        started = time.monotonic()
        completed = subprocess.run(
            argv,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        wall = time.monotonic() - started
        if completed.returncode != 0:
            return BackendOutcome(
                ran=False,
                total_tokens=0,
                tool_calls=0,
                wall_seconds=wall,
                final_diff_hash=None,
                notes=f"claude exit {completed.returncode}: {completed.stderr[:300]}",
                model=self._model or "claude-default",
            )
        try:
            report = json.loads(completed.stdout)
        except ValueError:
            return BackendOutcome(
                ran=False,
                total_tokens=0,
                tool_calls=0,
                wall_seconds=wall,
                final_diff_hash=None,
                notes="claude output was not valid JSON",
                model=self._model or "claude-default",
            )
        usage = report.get("usage") or {}
        return BackendOutcome(
            ran=True,
            total_tokens=int(
                usage.get("output_tokens", 0) + usage.get("input_tokens", 0)
            ),
            tool_calls=int(report.get("tool_use_count", 0) or 0),
            wall_seconds=wall,
            final_diff_hash=None,
            notes=(report.get("result") or "")[:300],
            model=report.get("model") or self._model or "claude-default",
        )


def make_backend(name: str) -> AgentBackend:
    if name == "dryrun":
        return DryRunBackend()
    if name == "claude-code":
        return ClaudeCodeBackend()
    raise ValueError(f"unknown backend: {name}")


__all__ = [
    "AgentBackend",
    "BackendOutcome",
    "ClaudeCodeBackend",
    "DryRunBackend",
    "make_backend",
]
