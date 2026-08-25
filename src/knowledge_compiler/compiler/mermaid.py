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


__all__ = [
    "compile_architecture_graph",
    "compile_flow_sequence",
    "mermaid_identifier",
    "mermaid_label",
]
