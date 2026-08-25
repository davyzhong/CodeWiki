from __future__ import annotations

import json
import os
from pathlib import Path

from knowledge_compiler.orchestrator.contracts import RunRecord


class RunStoreError(ValueError):
    """Raised when persisted run state cannot be saved or trusted."""


class RunStore:
    """Atomic single-active-run store under .knowledge/state/runs/<run-id>/."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)

    def _run_dir(self, run_id: str) -> Path:
        if "/" in run_id or run_id in {"", ".", ".."}:
            raise RunStoreError(f"unsafe run id: {run_id}")
        return self._root / run_id

    def save(self, record: RunRecord) -> None:
        record = RunRecord.model_validate(record.model_dump(mode="json"))
        if record.active:
            for existing in self._list_runs():
                if existing.run_id == record.run_id:
                    continue
                if existing.active:
                    raise RunStoreError(
                        "another active run holds the state: "
                        f"{existing.run_id}"
                    )
        run_dir = self._run_dir(record.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        )
        temporary = run_dir / "run.json.tmp"
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, run_dir / "run.json")

    def load(self, run_id: str) -> RunRecord:
        file = self._run_dir(run_id) / "run.json"
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise RunStoreError(f"run state unreadable: {error}") from error
        try:
            return RunRecord.model_validate(payload)
        except ValueError as error:
            raise RunStoreError(f"run state is tampered or invalid: {error}") from error

    def _list_runs(self) -> list[RunRecord]:
        records: list[RunRecord] = []
        if not self._root.exists():
            return records
        for directory in sorted(self._root.iterdir()):
            if not directory.is_dir() or directory.is_symlink():
                continue
            file = directory / "run.json"
            if not file.exists():
                continue
            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
                records.append(RunRecord.model_validate(payload))
            except (OSError, ValueError):
                continue
        return records

    def active_run(self) -> RunRecord | None:
        for record in self._list_runs():
            if record.active:
                return record
        return None


__all__ = ["RunStore", "RunStoreError"]
