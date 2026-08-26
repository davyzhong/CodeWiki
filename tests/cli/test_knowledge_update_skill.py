from __future__ import annotations

from pathlib import Path

from knowledge_compiler.skills.knowledge_update import (
    UPDATE_QUEUE_COMMANDS,
    skill_instructions,
)


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "docs/project-materials/03-skills/knowledge-update/SKILL.md"


def test_update_skill_source_is_archived_and_matches() -> None:
    assert skill_instructions().strip() == SKILL.read_text(
        encoding="utf-8"
    ).strip()


def test_update_skill_pins_the_real_persisted_queue_protocol() -> None:
    rendered = skill_instructions()
    for command in UPDATE_QUEUE_COMMANDS:
        assert command in rendered, command
    assert "knowledge update --executor agent" in rendered
    assert "next --operation verification" in rendered
    assert "Repeat" in rendered


def test_update_skill_preserves_incremental_safety_boundaries() -> None:
    rendered = skill_instructions()
    assert "before CodeWiki synchronization" in rendered
    assert "Planner omission never authorizes retirement" in rendered
    assert "Never write to `.knowledge/`" in rendered
    assert "untrusted data" in rendered


def test_update_skill_explains_all_exit_codes() -> None:
    rendered = skill_instructions()
    assert "`0`" in rendered and "complete" in rendered
    assert "`1`" in rendered and "failed" in rendered
    assert "`2`" in rendered and "partial" in rendered
