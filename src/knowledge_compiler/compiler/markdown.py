from __future__ import annotations

from collections.abc import Iterable

from knowledge_compiler.compiler.yaml import _validate_inputs
from knowledge_compiler.contracts.evidence import EvidenceItem, EvidencePack
from knowledge_compiler.contracts.knowledge import ModuleKnowledge


def _code(value: str) -> str:
    return f"`{value.replace('`', '\N{MODIFIER LETTER GRAVE ACCENT}')}`"


def _claim_evidence(
    claim_ids: Iterable[str],
    claims_by_id: dict[str, object],
    evidence_by_id: dict[str, EvidenceItem],
) -> tuple[str, str]:
    normalized_claim_ids = tuple(sorted(claim_ids))
    evidence_ids = sorted(
        {
            evidence_id
            for claim_id in normalized_claim_ids
            for evidence_id in claims_by_id[claim_id].evidence_ids
        }
    )
    claim_text = ", ".join(_code(claim_id) for claim_id in normalized_claim_ids)
    citations = ", ".join(
        _code(
            f"{evidence_by_id[evidence_id].path}:"
            f"{evidence_by_id[evidence_id].start_line}-"
            f"{evidence_by_id[evidence_id].end_line}"
        )
        for evidence_id in evidence_ids
    )
    return claim_text, citations


def _pointers(
    claim_ids: Iterable[str],
    claims_by_id: dict[str, object],
    evidence_by_id: dict[str, EvidenceItem],
    indent: str = "",
) -> list[str]:
    claims, citations = _claim_evidence(
        claim_ids, claims_by_id, evidence_by_id
    )
    return [
        f"{indent}- Claims: {claims}",
        f"{indent}- Evidence: {citations}",
    ]


def _context(module: ModuleKnowledge, pack: EvidencePack):
    canonical, validated_pack = _validate_inputs(module, pack)
    claims_by_id = {claim.id: claim for claim in canonical.claims}
    evidence_by_id = {item.id: item for item in validated_pack.evidence}
    return canonical, claims_by_id, evidence_by_id


def compile_module_card(
    module: ModuleKnowledge, evidence_pack: EvidencePack
) -> bytes:
    """Compile a compact, Claim-backed Markdown module card."""

    canonical, claims, evidence = _context(module, evidence_pack)
    lines = [
        f"# {canonical.title}",
        "",
        f"{_code(canonical.id)} · verified at {_code(canonical.validity.verified_commit)}",
        "",
        canonical.summary.text,
        "",
        *_pointers(canonical.summary.claim_ids, claims, evidence),
        "",
        "## Responsibilities",
        "",
    ]
    for item in canonical.responsibilities:
        lines.append(f"- {item.text}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    lines.extend(["", "## Public interfaces", ""])
    for item in canonical.public_interfaces:
        lines.append(f"- {_code(item.name)} — {item.description}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    lines.extend(["", "## Dependencies", ""])
    for item in canonical.dependencies:
        lines.append(f"- {_code(item.target)} — {item.description}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    lines.extend(["", "## Relations", ""])
    for item in canonical.relations:
        lines.append(f"- {item.predicate} → {item.target}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    return ("\n".join(lines) + "\n").encode("utf-8")


def compile_module_wiki(
    module: ModuleKnowledge, evidence_pack: EvidencePack
) -> bytes:
    """Compile a detailed, Claim-backed Markdown module wiki page."""

    canonical, claims, evidence = _context(module, evidence_pack)
    branch = canonical.scope.branch or "(detached)"
    lines = [
        f"# {canonical.title}",
        "",
        "## Scope",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Knowledge ID | {_code(canonical.id)} |",
        f"| Repository | {_code(canonical.scope.repository)} |",
        f"| Branch | {_code(branch)} |",
        f"| Commit | {_code(canonical.scope.commit)} |",
        f"| Validity | {_code(canonical.validity.status)} |",
        "",
        "## Summary",
        "",
        canonical.summary.text,
        "",
        *_pointers(canonical.summary.claim_ids, claims, evidence),
        "",
        "## Responsibilities",
        "",
    ]
    for item in canonical.responsibilities:
        lines.extend(
            [
                f"### {item.text}",
                "",
                *_pointers(item.claim_ids, claims, evidence),
                "",
            ]
        )
    lines.extend(["## Public interfaces", ""])
    for item in canonical.public_interfaces:
        lines.extend(
            [
                f"### {_code(item.name)}",
                "",
                item.description,
                "",
                *_pointers(item.claim_ids, claims, evidence),
                "",
            ]
        )
    lines.extend(["## Dependencies", ""])
    for item in canonical.dependencies:
        lines.extend(
            [
                f"### {_code(item.target)}",
                "",
                item.description,
                "",
                *_pointers(item.claim_ids, claims, evidence),
                "",
            ]
        )
    lines.extend(["## Relations", ""])
    for item in canonical.relations:
        lines.extend(
            [
                f"### {item.predicate} → {item.target}",
                "",
                *_pointers(item.claim_ids, claims, evidence),
                "",
            ]
        )
    lines.extend(["## Verified claims", ""])
    for claim in canonical.claims:
        _, citations = _claim_evidence((claim.id,), claims, evidence)
        lines.extend(
            [
                f"### {_code(claim.id)}",
                "",
                claim.statement,
                "",
                f"- Evidence: {citations}",
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


__all__ = ["compile_module_card", "compile_module_wiki"]
