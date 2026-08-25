from __future__ import annotations

import json
import os
import re
from pathlib import Path

from knowledge_compiler.orchestrator.contracts import RunRecord


_SAFE_COMPONENT = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,254}[A-Za-z0-9_-])?\Z"
)


class RunStoreError(ValueError):
    """Raised when persisted run state cannot be saved or trusted."""


class RunStore:
    """Atomic single-active-run store under .knowledge/state/runs/<run-id>/."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)

    def _run_dir(self, run_id: str) -> Path:
        if not _SAFE_COMPONENT.fullmatch(run_id) or run_id in {".", ".."}:
            raise RunStoreError(f"unsafe run id: {run_id}")
        return self._root / run_id

    def _target_dir(self, run_id: str, target_id: str) -> Path:
        if (
            not _SAFE_COMPONENT.fullmatch(target_id)
            or target_id in {".", ".."}
        ):
            raise RunStoreError(f"unsafe target id: {target_id}")
        return self._run_dir(run_id) / "targets" / target_id

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

    def save_extraction_context(
        self,
        run_id: str,
        target_id: str,
        request: object,
        result: object,
    ) -> None:
        from knowledge_compiler.contracts.knowledge import ExtractionResult
        from knowledge_compiler.contracts.semantic import ExtractionRequest

        validated_request = ExtractionRequest.model_validate(
            request.model_dump(mode="json")
        )
        validated_result = ExtractionResult.model_validate(
            result.model_dump(mode="json")
        )
        if (
            validated_request.run_id != run_id
            or validated_request.target_id != target_id
            or validated_result.run_id != run_id
            or validated_result.target_id != target_id
        ):
            raise RunStoreError(
                "extraction context identity does not match its run target"
            )
        target_dir = self._target_dir(run_id, target_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "request": validated_request.model_dump(mode="json"),
                "result": validated_result.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        temporary = target_dir / "extraction.json.tmp"
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, target_dir / "extraction.json")

    def load_extraction_context(
        self, run_id: str, target_id: str
    ) -> tuple[object, object]:
        from knowledge_compiler.contracts.knowledge import ExtractionResult
        from knowledge_compiler.contracts.semantic import ExtractionRequest

        path = self._target_dir(run_id, target_id) / "extraction.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            request = ExtractionRequest.model_validate(payload["request"])
            result = ExtractionResult.model_validate(payload["result"])
        except (KeyError, OSError, ValueError) as error:
            raise RunStoreError(
                f"extraction context unreadable: {error}"
            ) from error
        if (
            request.run_id != run_id
            or request.target_id != target_id
            or result.run_id != run_id
            or result.target_id != target_id
        ):
            raise RunStoreError(
                "extraction context identity does not match its run target"
            )
        return request, result

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
