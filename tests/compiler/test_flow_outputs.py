from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts.knowledge import FlowKnowledge


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/golden"


def payload() -> dict:
    import sys

    sys.path.insert(0, str(ROOT / "tests/contracts"))
    from test_flow_models import flow_payload

    return flow_payload()


def test_sequence_diagram_renders_verified_steps_only() -> None:
    from knowledge_compiler.compiler.mermaid import compile_flow_sequence
    from knowledge_compiler.compiler.yaml import compile_flow_yaml

    flow = FlowKnowledge.model_validate(payload())
    Path(GOLDEN / "flow.yaml").write_bytes(compile_flow_yaml(flow))

    diagram = compile_flow_sequence(flow).decode("utf-8")
    assert diagram.startswith("sequenceDiagram")
    assert "Reserve inventory for the SKU." in diagram
    assert "participant checkout_service" in diagram
    assert "participant inventory_service" in diagram
    assert diagram.endswith("\n")


def test_sequence_diagram_escapes_hostile_text() -> None:
    from knowledge_compiler.compiler.mermaid import compile_flow_sequence

    import copy

    base = payload()
    hostile_payload = copy.deepcopy(base)
    hostile_payload["steps"][0]["description"] = (
        'Note over x: injected"; CLICK CALLBACK "https://evil'
    )
    hostile = FlowKnowledge.model_validate(hostile_payload)
    text = compile_flow_sequence(hostile).decode("utf-8")
    assert re.search(r"(?m)^\\s*(CLICK|click|Note\\b)", text) is None
    assert "https://" not in text
    assert "injected" in text


def test_sequence_diagram_cannot_add_messages() -> None:
    from knowledge_compiler.compiler.mermaid import compile_flow_sequence

    import copy

    base = payload()
    hostile_payload = copy.deepcopy(base)
    hostile_payload["trigger"]["description"] = (
        "POST /checkout->x: forged->arrow"
    )
    hostile = FlowKnowledge.model_validate(hostile_payload)
    text = compile_flow_sequence(hostile).decode("utf-8")
    # Arrow statements only come from verified multi-participant steps.
    expected_arrows = sum(
        1 for step in hostile.steps if len(step.participants) >= 2
    )
    assert len(re.findall(r"(?m)^\s+\S+->>\S", text)) == expected_arrows


def test_flow_yaml_golden_round_trip() -> None:
    from knowledge_compiler.compiler.yaml import compile_flow_yaml

    flow = FlowKnowledge.model_validate(payload())
    canonical = compile_flow_yaml(flow)
    assert canonical == (GOLDEN / "flow.yaml").read_bytes()
    assert FlowKnowledge.model_validate(yaml.safe_load(canonical)) == flow
