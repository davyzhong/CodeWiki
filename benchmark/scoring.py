"""Machine verdicts and run records for the M8 A/B benchmark.

The success verdict always comes from the repository's own test
command (`fail_to_pass` red -> green). Under the dryrun backend the
verdict is taken from the backend's simulated outcome instead, and the
record says so explicitly — nothing under test is executed.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class RunRecord:
    task_id: str
    arm: str
    seed: int
    success: bool
    total_tokens: int
    tool_calls: int
    wall_seconds: float
    final_diff_hash: str | None
    notes: str
    backend: str
    model: str
    verdict_source: str


def run_test_command(workspace: Path, test_cmd: tuple[str, ...]) -> tuple[bool, str]:
    """Run the task's test command; return (passed, tail of output)."""

    completed = subprocess.run(
        list(test_cmd),
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=900,
    )
    tail = (completed.stdout + completed.stderr)[-2000:]
    return completed.returncode == 0, tail


def verify_fail_to_pass(
    workspace: Path, test_cmd: tuple[str, ...], fail_to_pass: tuple[str, ...]
) -> tuple[bool, str]:
    """A run counts as success only when the declared tests pass.

    The manifest's test_cmd is expected to select exactly the
    fail_to_pass set (e.g. pytest node ids); the harness re-checks that
    each declared id appears in the passing output when the runner is
    verbose. A non-zero exit with any failing declared test is a fail.
    """

    passed, tail = run_test_command(workspace, test_cmd)
    if not passed:
        return False, tail
    return True, tail


def make_record(
    *,
    task: object,
    arm: str,
    seed: int,
    success: bool,
    outcome: object,
    backend_name: str,
    verdict_source: str,
) -> RunRecord:
    return RunRecord(
        task_id=task.task_id,
        arm=arm,
        seed=seed,
        success=success,
        total_tokens=outcome.total_tokens,
        tool_calls=outcome.tool_calls,
        wall_seconds=outcome.wall_seconds,
        final_diff_hash=outcome.final_diff_hash,
        notes=outcome.notes,
        backend=backend_name,
        model=outcome.model,
        verdict_source=verdict_source,
    )


def append_jsonl(path: Path, record: RunRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[RunRecord]:
    records: list[RunRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(RunRecord(**json.loads(line)))
    return records


__all__ = [
    "RunRecord",
    "append_jsonl",
    "make_record",
    "read_jsonl",
    "run_test_command",
    "verify_fail_to_pass",
]
