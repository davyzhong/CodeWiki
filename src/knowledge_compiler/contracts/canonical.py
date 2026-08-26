from __future__ import annotations

from typing import Any


def parse_canonical_knowledge(payload: Any) -> object:
    """Parse one canonical object through its type discriminator."""

    from knowledge_compiler.contracts.knowledge import (
        ArchitectureKnowledge,
        FlowKnowledge,
        ModuleKnowledge,
        RuleKnowledge,
        TechStackKnowledge,
    )

    if not isinstance(payload, dict):
        raise ValueError("canonical object must be a mapping")
    models = {
        "architecture": ArchitectureKnowledge,
        "module": ModuleKnowledge,
        "flow": FlowKnowledge,
        "rule": RuleKnowledge,
        "tech-stack": TechStackKnowledge,
    }
    model = models.get(payload.get("type"))
    if model is None:
        raise ValueError("unknown canonical object type")
    return model.model_validate(payload)


__all__ = ["parse_canonical_knowledge"]
