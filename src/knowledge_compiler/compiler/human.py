from __future__ import annotations

from collections.abc import Callable, Iterable

from knowledge_compiler.contracts.human import HumanOverlay


Escaper = Callable[[str], str]


def render_overlay_field(
    machine_lines: Iterable[str],
    *,
    overlay: HumanOverlay | None,
    field: str,
    escape: Escaper,
) -> list[str]:
    """Apply one overlay section to rendered text, never canonical IR."""

    original = list(machine_lines)
    if overlay is None:
        return original
    section = next(
        (item for item in overlay.sections if item.field == field), None
    )
    if section is None:
        return original
    human = [
        f"> source: human · updated {_timestamp(overlay)} · "
        f"basis: {escape(section.basis)}",
        ">",
        f"> {escape(section.text)}",
    ]
    if section.mode == "supplement":
        return [*original, "", "### Human supplement", "", *human]
    return [
        *human,
        "",
        "<details>",
        "<summary>Machine-verified original</summary>",
        "",
        *original,
        "",
        "</details>",
    ]


def render_overlay_notes(
    overlay: HumanOverlay | None, *, escape: Escaper
) -> list[str]:
    if overlay is None or not overlay.notes:
        return []
    lines = ["", "## Human notes", ""]
    for note in overlay.notes:
        lines.extend(
            [
                f"### {escape(note.id)}",
                "",
                f"> source: human · updated {_timestamp(overlay)} · "
                f"basis: {escape(note.basis)}",
                ">",
                f"> {escape(note.text)}",
                "",
            ]
        )
    return lines


def _timestamp(overlay: HumanOverlay) -> str:
    return overlay.updated_at.isoformat()


__all__ = ["render_overlay_field", "render_overlay_notes"]
