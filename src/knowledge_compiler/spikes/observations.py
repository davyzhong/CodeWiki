from pathlib import Path
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandObservation(BaseModel):
    name: str
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    json_value: Any | None = None


class McpObservation(BaseModel):
    name: str
    tool_name: str
    arguments: dict[str, Any]
    is_error: bool
    structured_content: Any | None = None
    text_content: list[str] = Field(default_factory=list)


class ProbeBundle(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    codewiki_version: str | None
    repository_commit: str
    commands: list[CommandObservation]
    mcp: list[McpObservation] = Field(default_factory=list)


SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s]+)")


def sanitize_text(text: str, repo_root: Path) -> str:
    sanitized = text.replace(str(repo_root), "<REPO>")
    return SECRET_PATTERN.sub(r"\1<REDACTED>", sanitized)


def write_bundle(bundle: ProbeBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
