from __future__ import annotations

from pathlib import Path

import knowledge_compiler.skills as _package

_SKILL_DIR = Path(_package.__file__).resolve().parent / "knowledge_build"
QUEUE_COMMANDS = (
    "knowledge prepare",
    "knowledge next",
    "knowledge evidence",
    "knowledge submit-extraction",
    "knowledge verify-next",
    "knowledge submit-verification",
    "knowledge finalize",
)


def skill_instructions() -> str:
    source = _SKILL_DIR / "SKILL.md"
    return source.read_text(encoding="utf-8")


__all__ = ["QUEUE_COMMANDS", "skill_instructions"]
