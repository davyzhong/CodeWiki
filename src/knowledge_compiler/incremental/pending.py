from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PersistedTarget(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    target_id: str
    reason: str


class PendingStore:
    """Persist unresolved required targets so retries happen even with no
    new file diff on the next update."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._targets: dict[str, PersistedTarget] = {}
        if self._path.exists():
            self._targets = self._load()

    def _load(self) -> dict[str, PersistedTarget]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"pending store unreadable: {error}") from error
        if not isinstance(payload, list):
            raise ValueError("pending store must be a list")
        return {
            item["target_id"]: PersistedTarget.model_validate(item)
            for item in payload
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [target.model_dump(mode="json") for target in self.targets]
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self._path)

    @property
    def targets(self) -> tuple[PersistedTarget, ...]:
        return tuple(sorted(self._targets.values(), key=lambda t: t.target_id))

    def target_ids(self) -> set[str]:
        return set(self._targets)

    def add(self, target: PersistedTarget) -> None:
        self._targets[target.target_id] = target
        self._save()

    def resolve(self, target_id: str) -> None:
        self._targets.pop(target_id, None)
        self._save()


__all__ = ["PendingStore", "PersistedTarget"]
