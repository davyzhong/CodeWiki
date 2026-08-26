from __future__ import annotations

from pathlib import Path

import knowledge_compiler.skills as _package


_SKILL_DIR = Path(_package.__file__).resolve().parent / "knowledge_update"
UPDATE_QUEUE_COMMANDS = (
    "knowledge update --executor agent",
    "knowledge next --operation extraction",
    "knowledge evidence",
    "knowledge submit-extraction",
    "knowledge verify-next",
    "knowledge next --operation verification",
    "knowledge submit-verification",
    "knowledge finalize",
)


def skill_instructions() -> str:
    return (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


__all__ = ["UPDATE_QUEUE_COMMANDS", "skill_instructions"]
