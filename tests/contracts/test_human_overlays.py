from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts.human import (
    HumanNote,
    HumanOverlay,
    HumanSection,
)


def overlay(**overrides: object) -> dict:
    values: dict[str, object] = {
        "schema_version": "0.1",
        "object_id": "module.shop.checkout",
        "updated_at": "2026-08-25T12:00:00+08:00",
        "sections": [
            {
                "field": "summary",
                "mode": "supplement",
                "text": "Checkout holds a repository-wide lock during peak season.",
                "basis": "postmortem 2026-07",
            }
        ],
        "notes": [
            {
                "id": "module.shop.checkout.note.peak-load",
                "text": "Reservation contention rises during promotions.",
                "basis": "operations experience",
            }
        ],
    }
    values.update(overrides)
    return values


def test_overlay_round_trips() -> None:
    parsed = HumanOverlay.model_validate(overlay())
    assert parsed.object_id == "module.shop.checkout"
    assert parsed.sections[0].mode == "supplement"
    assert parsed.notes[0].id == "module.shop.checkout.note.peak-load"


def test_overlay_rejects_unknown_mode() -> None:
    payload = overlay()
    payload["sections"][0]["mode"] = "replace"
    with pytest.raises(ValueError, match="mode"):
        HumanOverlay.model_validate(payload)


def test_overlay_rejects_unknown_field() -> None:
    payload = overlay()
    payload["sections"][0]["field"] = "hologram"
    with pytest.raises(ValueError, match="field"):
        HumanOverlay.model_validate(payload)


def test_overlay_rejects_naive_timestamp() -> None:
    payload = overlay()
    payload["updated_at"] = "2026-08-25T12:00:00"
    with pytest.raises(ValueError, match="timezone"):
        HumanOverlay.model_validate(payload)


def test_overlay_rejects_duplicate_note_ids() -> None:
    payload = overlay()
    payload["notes"].append(dict(payload["notes"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        HumanOverlay.model_validate(payload)


def test_overlay_rejects_note_id_not_owned_by_object() -> None:
    payload = overlay()
    payload["notes"][0]["id"] = "module.shop.inventory.note.peak"
    with pytest.raises(ValueError, match="object"):
        HumanOverlay.model_validate(payload)


def test_overlay_rejects_extra_keys() -> None:
    payload = overlay()
    payload["surprise"] = True
    with pytest.raises(ValueError):
        HumanOverlay.model_validate(payload)


def test_supplement_mode_is_default() -> None:
    section = HumanSection.model_validate(
        {
            "field": "summary",
            "text": "A supplement.",
            "basis": "experience",
        }
    )
    assert section.mode == "supplement"


def test_override_mode_allowed() -> None:
    section = HumanSection.model_validate(
        {
            "field": "summary",
            "mode": "override",
            "text": "A human replacement.",
            "basis": "postmortem",
        }
    )
    assert section.mode == "override"


def test_empty_notes_allowed() -> None:
    parsed = HumanOverlay.model_validate(overlay(notes=[]))
    assert parsed.notes == ()
