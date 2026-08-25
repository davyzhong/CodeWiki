from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.skills.knowledge_build import (
    QUEUE_COMMANDS,
    skill_instructions,
)


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "docs/project-materials/03-skills/knowledge-build/SKILL.md"


def test_skill_source_is_archived_and_matches() -> None:
    source = SKILL.read_text(encoding="utf-8")
    rendered = skill_instructions()
    assert rendered.strip() == source.strip()


def test_skill_protocol_covers_every_queue_command() -> None:
    rendered = skill_instructions()
    for command in QUEUE_COMMANDS:
        assert command in rendered, command


def test_skill_never_schedules_or_publishes() -> None:
    rendered = skill_instructions()
    assert "Never implement your own scheduling" in rendered
    assert "orchestrator" in rendered
    assert "publication" in rendered
    # The skill must treat repository text as data.
    assert "untrusted data" in rendered
    assert "never as instructions" in rendered or "never an instruction" in rendered


def test_skill_mentions_interruption_resume() -> None:
    rendered = skill_instructions()
    assert "resumes" in rendered or "resume" in rendered
