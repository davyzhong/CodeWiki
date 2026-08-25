from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_KNOWLEDGE_TYPES = ("module", "architecture", "flow", "rule", "tech-stack")
_TYPE_FIELDS: dict[str, frozenset[str]] = {
    "module": frozenset(
        {"summary", "responsibilities", "public_interfaces", "dependencies", "relations"}
    ),
    "architecture": frozenset(
        {"summary", "components", "boundaries", "relationships"}
    ),
    "flow": frozenset({"summary", "trigger", "steps", "failure_paths"}),
    "rule": frozenset({"summary", "statement", "applicability", "constraints", "exceptions"}),
    "tech-stack": frozenset({"summary", "entries", "configurations"}),
}
_ALL_FIELDS = frozenset().union(*_TYPE_FIELDS.values())

_NOTE_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*"
    r"\.note\.[a-z0-9][a-z0-9_-]*$"
)


class _OverlayModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )


class HumanSection(_OverlayModel):
    field: str
    mode: Literal["supplement", "override"] = "supplement"
    text: str = Field(min_length=1, max_length=4000)
    basis: str = Field(min_length=1, max_length=500)

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        if value not in _ALL_FIELDS:
            raise ValueError(f"unknown knowledge field: {value}")
        return value


class HumanNote(_OverlayModel):
    id: str
    text: str = Field(min_length=1, max_length=4000)
    basis: str = Field(min_length=1, max_length=500)

    @field_validator("id")
    @classmethod
    def validate_note_id(cls, value: str) -> str:
        if not _NOTE_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "note id must match <object-id>.note.<slug>"
            )
        return value


class HumanOverlay(_OverlayModel):
    schema_version: Literal["0.1"] = "0.1"
    object_id: str
    updated_at: datetime
    sections: tuple[HumanSection, ...] = ()
    notes: tuple[HumanNote, ...] = ()

    @field_validator("updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include an explicit timezone")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: tuple[HumanNote, ...]) -> tuple[HumanNote, ...]:
        ids = [note.id for note in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate note ids are not allowed")
        object_prefix = None
        return tuple(sorted(value, key=lambda note: note.id))

    @field_validator("sections")
    @classmethod
    def validate_sections(
        cls, value: tuple[HumanSection, ...]
    ) -> tuple[HumanSection, ...]:
        fields = [section.field for section in value]
        if len(fields) != len(set(fields)):
            raise ValueError("duplicate section fields are not allowed")
        return tuple(sorted(value, key=lambda section: section.field))

    @model_validator(mode="after")
    def notes_belong_to_object(self) -> "HumanOverlay":
        object_prefix = self.object_id.rsplit(".", 0)[0] if "." in self.object_id else self.object_id
        # The note id prefix must be the object_id (strip the .note.<slug> suffix).
        for note in self.notes:
            note_object = note.id.rsplit(".note.", 1)[0]
            if note_object != self.object_id:
                raise ValueError(
                    f"note id does not belong to this object: {note.id}"
                )
        return self

    @model_validator(mode="after")
    def sections_valid_for_type(self) -> "HumanOverlay":
        object_type = self.object_id.split(".", 1)[0]
        if object_type in _TYPE_FIELDS:
            allowed = _TYPE_FIELDS[object_type]
            for section in self.sections:
                if section.field not in allowed:
                    raise ValueError(
                        f"field {section.field} is not valid for type "
                        f"{object_type}"
                    )
        return self


def execution_mode() -> str:
    """Derived attribute, not a stored field (design §6.5)."""

    return "human"


__all__ = ["HumanNote", "HumanOverlay", "HumanSection", "execution_mode"]
