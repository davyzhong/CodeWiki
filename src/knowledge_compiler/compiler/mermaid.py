from __future__ import annotations

import re

from knowledge_compiler.contracts.knowledge import ArchitectureKnowledge


_SAFE_IDENTIFIER = re.compile(r"[^A-Za-z0-9_]")
_SAFE_LABEL = re.compile(r"[\x00-\x1f\x7f-\x9f\"<>&'`]")


def mermaid_identifier(value: str) -> str:
    cleaned = _SAFE_IDENTIFIER.sub("_", value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "n" + cleaned
    return cleaned


_URL_SCHEME = re.compile(r"https?://")


def mermaid_label(value: str) -> str:
    cleaned = _SAFE_LABEL.sub("", value)
    cleaned = cleaned.replace('"', "'")
    cleaned = _URL_SCHEME.sub("", cleaned)
    return cleaned[:120]


def compile_architecture_graph(architecture: ArchitectureKnowledge) -> bytes:
    """Render a deterministic, escaped Mermaid graph from verified fields."""

    validated = ArchitectureKnowledge.model_validate(
        architecture.model_dump(mode="json")
    )
    lines = ["graph TD"]
    for component in validated.components:
        lines.append(
            f"    {mermaid_identifier(component.name)}"
            f"[\"{mermaid_label(component.responsibility)}\"]"
        )
    for relationship in validated.relationships:
        lines.append(
            f"    {mermaid_identifier(relationship.source)} -->|"
            f"{mermaid_label(relationship.predicate)}|"
            f"{mermaid_identifier(relationship.target)}"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def compile_flow_sequence(flow) -> bytes:
    """Render a deterministic, escaped Mermaid sequence diagram."""

    from knowledge_compiler.contracts.knowledge import FlowKnowledge

    validated = FlowKnowledge.model_validate(flow.model_dump(mode="json"))
    lines = ["sequenceDiagram"]
    for step in validated.steps:
        participants = [mermaid_identifier(p) for p in step.participants]
        for participant in participants:
            lines.append(f"    participant {participant}")
        if len(participants) >= 2:
            lines.append(
                f"    {participants[0]}->>{participants[1]}: "
                f"{mermaid_label(step.description)}"
            )
        else:
            lines.append(
                f"    Note over {participants[0]}: "
                f"{mermaid_label(step.description)}"
            )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _svg_text(value: str, limit: int) -> str:
    from html import escape

    return escape(mermaid_label(value)[:limit], quote=True)


def render_architecture_graph_svg(architecture) -> bytes:
    """Render the same graph as deterministic SVG boxes and arrows."""

    from knowledge_compiler.contracts.knowledge import ArchitectureKnowledge

    validated = ArchitectureKnowledge.model_validate(
        architecture.model_dump(mode="json")
    )
    names = sorted(
        {component.name for component in validated.components}
        | {item.source for item in validated.relationships}
        | {item.target for item in validated.relationships}
    )
    order = {name: index for index, name in enumerate(names)}
    node_width, node_height, gap = 300, 60, 30
    svg_height = 40 + len(names) * (node_height + gap)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="520" '
        f'height="{svg_height}" role="img" aria-label="architecture graph">'
    ]
    node_geometry: dict[str, tuple[int, int]] = {}
    for name in names:
        top = 40 + order[name] * (node_height + gap)
        node_geometry[name] = (top, top + node_height)
        parts.append(
            f'<rect x="40" y="{top}" width="{node_width}" '
            f'height="{node_height}" rx="8" fill="#f6f8fa" '
            'stroke="#d0d7de"/>'
        )
        parts.append(
            f'<text x="56" y="{top + 24}" font-size="14" '
            f'font-weight="bold">{_svg_text(name, 34)}</text>'
        )
    for index, relationship in enumerate(validated.relationships):
        if (
            relationship.source not in node_geometry
            or relationship.target not in node_geometry
        ):
            continue
        source_top, source_bottom = node_geometry[relationship.source]
        target_top, target_bottom = node_geometry[relationship.target]
        start_y = (source_top + source_bottom) // 2
        end_y = (target_top + target_bottom) // 2
        lane = 380 + (index % 6) * 24
        parts.append(
            f'<path d="M 340 {start_y} C {lane} {start_y}, {lane} {end_y}, '
            f'340 {end_y}" fill="none" stroke="#57606a" '
            'marker-end="url(#arrow)"/>'
        )
        parts.append(
            f'<text x="{lane + 4}" y="{(start_y + end_y) // 2}" '
            f'font-size="11" fill="#57606a">'
            f"{_svg_text(relationship.predicate, 24)}</text>"
        )
    parts.insert(
        1,
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#57606a"/></marker></defs>',
    )
    parts.append("</svg>")
    return ("\n".join(parts) + "\n").encode("utf-8")


def render_flow_sequence_svg(flow) -> bytes:
    """Render the same sequence as a deterministic SVG swimlane."""

    from knowledge_compiler.contracts.knowledge import FlowKnowledge

    validated = FlowKnowledge.model_validate(flow.model_dump(mode="json"))
    participants: list[str] = []
    for step in validated.steps:
        for participant in step.participants:
            if participant not in participants:
                participants.append(participant)
    lane_x = {
        participant: 60 + index * 200
        for index, participant in enumerate(participants)
    }
    svg_height = 120 + len(validated.steps) * 60
    svg_width = max(240, 60 + len(participants) * 200)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" '
        f'height="{svg_height}" role="img" aria-label="flow sequence">'
    ]
    for participant in participants:
        x = lane_x[participant]
        parts.append(
            f'<rect x="{x - 80}" y="20" width="160" height="34" rx="8" '
            'fill="#f6f8fa" stroke="#d0d7de"/>'
        )
        parts.append(
            f'<text x="{x}" y="42" font-size="13" text-anchor="middle">'
            f"{_svg_text(participant, 20)}</text>"
        )
        parts.append(
            f'<line x1="{x}" y1="54" x2="{x}" y2="{svg_height - 20}" '
            'stroke="#d0d7de" stroke-dasharray="4 4"/>'
        )
    for index, step in enumerate(validated.steps):
        del index
        y = 100 + step.order * 40
        ordered = sorted(step.participants)
        description = f"{step.order}. {step.description}"
        if len(ordered) >= 2:
            start_x = lane_x[ordered[0]]
            end_x = lane_x[ordered[1]]
            parts.append(
                f'<line x1="{start_x}" y1="{y}" x2="{end_x}" y2="{y}" '
                'stroke="#57606a" marker-end="url(#arrow)"/>'
            )
            text_x = (start_x + end_x) // 2
        else:
            text_x = lane_x[ordered[0]]
        parts.append(
            f'<text x="{text_x}" y="{y - 8}" font-size="11" '
            f'text-anchor="middle">{_svg_text(description, 60)}</text>'
        )
    parts.insert(
        1,
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#57606a"/></marker></defs>',
    )
    parts.append("</svg>")
    return ("\n".join(parts) + "\n").encode("utf-8")


__all__ = [
    "compile_architecture_graph",
    "compile_flow_sequence",
    "mermaid_identifier",
    "mermaid_label",
    "render_architecture_graph_svg",
    "render_flow_sequence_svg",
]
