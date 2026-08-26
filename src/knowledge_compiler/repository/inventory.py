from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class FileRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    path: str
    blob_id: str | None = None
    content_hash: str
    size: int
    language: str | None = None


def save_baseline(path: str | Path, records: tuple[FileRecord, ...]) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.model_dump(mode="json") for record in records]
    temporary = file.with_suffix(file.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, file)


def load_baseline(path: str | Path) -> tuple[FileRecord, ...]:
    file = Path(path)
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"baseline unreadable: {error}") from error
    if not isinstance(payload, list):
        raise ValueError("baseline must be a list of file records")
    return tuple(FileRecord.model_validate(item) for item in payload)


__all__ = ["FileRecord", "load_baseline", "save_baseline"]
