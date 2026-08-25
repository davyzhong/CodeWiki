from __future__ import annotations

import re
from pathlib import Path

import pytest

from knowledge_compiler.contracts.knowledge import ArchitectureKnowledge


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/golden"


def payload() -> dict:
    import json

    import yaml

    return yaml.safe_load((GOLDEN / "architecture.yaml").read_text(encoding="utf-8"))


def test_mermaid_renders_only_verified_relationships() -> None:
    from knowledge_compiler.compiler.mermaid import compile_architecture_graph

    architecture = ArchitectureKnowledge.model_validate(_payload())
    diagram = compile_architecture_graph(architecture)
    assert isinstance(diagram, bytes)
    text = diagram.decode("utf-8")
    assert text.startswith("graph TD")
    assert "checkout_service" in text
    assert "inventory_service" in text
    assert "Orchestrates checkout." in text
    assert text.endswith("\n")


def _payload() -> dict:
    import yaml

    return yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "tests/golden/architecture.yaml")
        .read_text(encoding="utf-8")
    )


def test_mermaid_escapes_hostile_identifiers_and_labels() -> None:
    from knowledge_compiler.compiler.mermaid import compile_architecture_graph

    base = _payload()
    hostile = ArchitectureKnowledge.model_validate(
        {
            **base,
            "components": [
                {
                    "name": 'evil"; CLICK CALLBACK "https://evil',
                    "responsibility": "x",
                    "claim_ids": [base["claims"][0]["id"]],
                }
            ],
            "relationships": [],
        }
    )
    text = compile_architecture_graph(hostile).decode("utf-8")
    # No Mermaid directive can start a line; hostile URL fully stripped.
    assert re.search(r"(?m)^\s*(CLICK|click|classDef|init|callback)\b", text) is None
    assert "https://" not in text
    assert "evil" in text  # sanitized but still present as inert text


def test_mermaid_cannot_inject_extra_edges() -> None:
    from knowledge_compiler.compiler.mermaid import compile_architecture_graph

    base = _payload()
    hostile = ArchitectureKnowledge.model_validate(
        {
            **base,
            "boundaries": [
                {
                    "name": "b --> secretTarget",
                    "description": "innocent",
                    "claim_ids": [base["claims"][0]["id"]],
                }
            ],
        }
    )
    text = compile_architecture_graph(hostile).decode("utf-8")
    edge_count = len(re.findall(r"-->", text))
    assert edge_count == len(hostile.relationships)


def test_architecture_yaml_golden_round_trip() -> None:
    architecture = ArchitectureKnowledge.model_validate(_payload())
    from knowledge_compiler.compiler.yaml import compile_architecture_yaml

    assert compile_architecture_yaml(architecture) == (
        GOLDEN / "architecture.yaml"
    ).read_bytes()
