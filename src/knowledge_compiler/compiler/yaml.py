from __future__ import annotations

from pathlib import Path

import yaml
from pydantic_core import PydanticSerializationError

from knowledge_compiler.contracts.evidence import EvidencePack
from knowledge_compiler.contracts.knowledge import ModuleKnowledge


class CompilerInputError(ValueError):
    """Raised when compiler inputs do not form a trusted canonical pair."""


def _revalidate_module(value: object) -> ModuleKnowledge:
    if not isinstance(value, ModuleKnowledge):
        raise CompilerInputError("module must be a verified canonical ModuleKnowledge")
    try:
        return ModuleKnowledge.model_validate(value.model_dump(mode="json"))
    except (PydanticSerializationError, TypeError, ValueError) as error:
        raise CompilerInputError("module contract dump/revalidation failed") from error


def _revalidate_pack(value: object) -> EvidencePack:
    if not isinstance(value, EvidencePack):
        raise CompilerInputError("evidence pack must be an EvidencePack")
    try:
        return EvidencePack.model_validate(value.model_dump(mode="json"))
    except (PydanticSerializationError, TypeError, ValueError) as error:
        raise CompilerInputError(
            "evidence pack contract dump/revalidation failed"
        ) from error


def _validate_inputs(
    module: ModuleKnowledge, evidence_pack: EvidencePack
) -> tuple[ModuleKnowledge, EvidencePack]:
    canonical = _revalidate_module(module)
    pack = _revalidate_pack(evidence_pack)

    if canonical.validity.status != "verified":
        raise CompilerInputError("module validity must be verified")
    if canonical.id != pack.target.id:
        raise CompilerInputError("module and Evidence Pack target identities differ")

    scope = canonical.scope
    repository = pack.repository
    identity_fields = (
        ("repository", scope.repository, repository.repository_id),
        ("root", Path(scope.root), Path(repository.root)),
        ("branch", scope.branch, repository.branch),
        ("commit", scope.commit, repository.commit),
        ("dirty", scope.dirty, repository.dirty),
        ("working_tree_hash", scope.working_tree_hash, repository.working_tree_hash),
    )
    mismatches = [name for name, actual, expected in identity_fields if actual != expected]
    if mismatches:
        raise CompilerInputError(
            "module and Evidence Pack repository identity differ: "
            + ", ".join(mismatches)
        )
    if canonical.validity.verified_commit != repository.commit:
        raise CompilerInputError("module verified commit differs from Evidence Pack commit")

    evidence_by_id = {item.id: item for item in pack.evidence}
    for claim in canonical.claims:
        for evidence_id, excerpt_hash in zip(
            claim.verification.evidence_ids,
            claim.verification.excerpt_hashes,
            strict=True,
        ):
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                raise CompilerInputError(
                    f"claim {claim.id} cites Evidence outside the Evidence Pack"
                )
            if excerpt_hash != evidence.excerpt_hash:
                raise CompilerInputError(
                    f"claim {claim.id} excerpt hash differs from the Evidence Pack"
                )
    return canonical, pack


def compile_module_yaml(
    module: ModuleKnowledge, evidence_pack: EvidencePack
) -> bytes:
    """Compile canonical ModuleKnowledge to deterministic UTF-8 YAML bytes."""

    canonical, _ = _validate_inputs(module, evidence_pack)
    text = yaml.safe_dump(
        canonical.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    return text.encode("utf-8")


def compile_architecture_yaml(architecture: object) -> bytes:
    """Compile canonical ArchitectureKnowledge to deterministic YAML bytes."""

    from knowledge_compiler.contracts.knowledge import ArchitectureKnowledge

    if not isinstance(architecture, ArchitectureKnowledge):
        raise CompilerInputError(
            "input must be a verified canonical ArchitectureKnowledge"
        )
    try:
        canonical = ArchitectureKnowledge.model_validate(
            architecture.model_dump(mode="json")
        )
    except (PydanticSerializationError, TypeError, ValueError) as error:
        raise CompilerInputError(
            "architecture contract dump/revalidation failed"
        ) from error
    if canonical.validity.status != "verified":
        raise CompilerInputError("architecture validity must be verified")
    text = yaml.safe_dump(
        canonical.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    return text.encode("utf-8")


def compile_flow_yaml(flow: object) -> bytes:
    """Compile canonical FlowKnowledge to deterministic YAML bytes."""

    from knowledge_compiler.contracts.knowledge import FlowKnowledge

    if not isinstance(flow, FlowKnowledge):
        raise CompilerInputError("input must be a verified canonical FlowKnowledge")
    try:
        canonical = FlowKnowledge.model_validate(flow.model_dump(mode="json"))
    except (PydanticSerializationError, TypeError, ValueError) as error:
        raise CompilerInputError("flow contract dump/revalidation failed") from error
    if canonical.validity.status != "verified":
        raise CompilerInputError("flow validity must be verified")
    text = yaml.safe_dump(
        canonical.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    return text.encode("utf-8")


def _compile_typed_yaml(model_type, value: object, label: str) -> bytes:
    if not isinstance(value, model_type):
        raise CompilerInputError(f"input must be a verified canonical {label}")
    try:
        canonical = model_type.model_validate(value.model_dump(mode="json"))
    except (PydanticSerializationError, TypeError, ValueError) as error:
        raise CompilerInputError(
            f"{label} contract dump/revalidation failed"
        ) from error
    if canonical.validity.status != "verified":
        raise CompilerInputError(f"{label} validity must be verified")
    text = yaml.safe_dump(
        canonical.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    return text.encode("utf-8")


def compile_rule_yaml(rule: object) -> bytes:
    from knowledge_compiler.contracts.knowledge import RuleKnowledge

    return _compile_typed_yaml(RuleKnowledge, rule, "RuleKnowledge")


def compile_rule_card(rule: object, overlay: object | None = None) -> bytes:
    from knowledge_compiler.compiler.human import (
        render_overlay_field,
        render_overlay_notes,
    )
    from knowledge_compiler.compiler.markdown import _code, _text
    from knowledge_compiler.contracts.knowledge import RuleKnowledge

    canonical = RuleKnowledge.model_validate(rule.model_dump(mode="json"))
    lines = [
        f"# {_text(canonical.title)}",
        "",
        f"{_code(canonical.id)} · {canonical.severity}",
        "",
    ]
    lines.extend(render_overlay_field(
        [
            _text(canonical.summary.text),
            "",
            f"- Claims: {_code(', '.join(canonical.summary.claim_ids))}",
        ],
        overlay=overlay,
        field="summary",
        escape=_text,
    ))
    lines.extend(["", "## Statement", ""])
    lines.extend(render_overlay_field(
        [
            _text(canonical.statement.text),
            "",
            f"- Claims: {_code(', '.join(canonical.statement.claim_ids))}",
        ],
        overlay=overlay,
        field="statement",
        escape=_text,
    ))
    applicability = [f"- {_code(path)}" for path in canonical.applicability.paths]
    lines.extend(["", "## Applicability", ""])
    lines.extend(render_overlay_field(
        applicability,
        overlay=overlay,
        field="applicability",
        escape=_text,
    ))
    if canonical.constraints:
        constraints = []
        for constraint in canonical.constraints:
            constraints.append(f"- {_text(constraint.description)}")
            constraints.append(
                f"  - Claims: {_code(', '.join(constraint.claim_ids))}"
            )
        lines.extend(["", "## Constraints", ""])
        lines.extend(render_overlay_field(
            constraints,
            overlay=overlay,
            field="constraints",
            escape=_text,
        ))
    if canonical.exceptions:
        exceptions = []
        for exception in canonical.exceptions:
            exceptions.append(f"- {_text(exception.description)}")
        lines.extend(["", "## Exceptions", ""])
        lines.extend(render_overlay_field(
            exceptions,
            overlay=overlay,
            field="exceptions",
            escape=_text,
        ))
    if canonical.related_objects:
        lines.extend(["", "## Related", ""])
        for target in canonical.related_objects:
            lines.append(f"- {_code(target)}")
    lines.extend(render_overlay_notes(overlay, escape=_text))
    return ("\n".join(lines) + "\n").encode("utf-8")


def compile_tech_stack_yaml(stack: object) -> bytes:
    from knowledge_compiler.contracts.knowledge import TechStackKnowledge

    return _compile_typed_yaml(TechStackKnowledge, stack, "TechStackKnowledge")


def compile_tech_stack_card(stack: object, overlay: object | None = None) -> bytes:
    from knowledge_compiler.compiler.human import (
        render_overlay_field,
        render_overlay_notes,
    )
    from knowledge_compiler.compiler.markdown import _code, _text
    from knowledge_compiler.contracts.knowledge import TechStackKnowledge

    canonical = TechStackKnowledge.model_validate(stack.model_dump(mode="json"))
    lines = [
        f"# {_text(canonical.title)}",
        "",
        f"{_code(canonical.id)} · verified at "
        f"{_code(canonical.validity.verified_commit)}",
        "",
    ]
    lines.extend(render_overlay_field(
        [_text(canonical.summary.text)],
        overlay=overlay,
        field="summary",
        escape=_text,
    ))
    technologies = []
    for entry in canonical.entries:
        technologies.append(
            f"- {_code(entry.name)} — {_text(entry.category)} · version "
            f"{_code(entry.version)} · {_text(entry.scope)}"
        )
    lines.extend(["", "## Technologies", ""])
    lines.extend(render_overlay_field(
        technologies,
        overlay=overlay,
        field="entries",
        escape=_text,
    ))
    if canonical.configurations:
        configurations = []
        for configuration in canonical.configurations:
            configurations.append(
                f"- {_code(configuration.path)} — "
                f"{_text(configuration.description)}"
            )
        lines.extend(["", "## Configuration evidence", ""])
        lines.extend(render_overlay_field(
            configurations,
            overlay=overlay,
            field="configurations",
            escape=_text,
        ))
    lines.extend(render_overlay_notes(overlay, escape=_text))
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = [
    "CompilerInputError",
    "compile_architecture_yaml",
    "compile_flow_yaml",
    "compile_module_yaml",
    "compile_rule_card",
    "compile_rule_yaml",
    "compile_tech_stack_card",
    "compile_tech_stack_yaml",
]
