from __future__ import annotations

import html
import re
from collections.abc import Iterable

from knowledge_compiler.compiler.yaml import _validate_inputs
from knowledge_compiler.contracts.evidence import EvidenceItem, EvidencePack
from knowledge_compiler.contracts.knowledge import ModuleKnowledge


def _visible_text(value: str) -> str:
    normalized = re.sub(r"\r\n?|\n", " ⏎ ", value)
    return html.escape(normalized, quote=False)


def _text(value: str) -> str:
    escaped = _visible_text(value)
    leading_indent = re.match(r"[ \t]+", escaped)
    if leading_indent:
        visible_indent = "".join(
            "&#32;" if character == " " else "&#9;"
            for character in leading_indent.group(0)
        )
        escaped = visible_indent + escaped[leading_indent.end() :]
    escaped = escaped.replace("\\", "\\\\")
    escaped = re.sub(r"([`*_~\-\[\]()|])", r"\\\1", escaped)
    if escaped.startswith("="):
        escaped = "&#61;" + escaped[1:]
    if re.match(r"^(?:#{1,6}(?:\s|$)|>|[-+]\s|\d+[.)]\s)", escaped):
        escaped = "\\" + escaped
    return escaped


def _code(value: str) -> str:
    content = _visible_text(value).replace("|", r"\|")
    runs = [len(match.group(0)) for match in re.finditer(r"`+", content)]
    fence = "`" * (max(runs, default=0) + 1)
    if content.startswith(("`", " ")) or content.endswith(("`", " ")):
        content = f" {content} "
    return f"{fence}{content}{fence}"


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
        f"# {_text(canonical.title)}",
        "",
        f"{_code(canonical.id)} · verified at {_code(canonical.validity.verified_commit)}",
        "",
        _text(canonical.summary.text),
        "",
        *_pointers(canonical.summary.claim_ids, claims, evidence),
        "",
        "## Responsibilities",
        "",
    ]
    for item in canonical.responsibilities:
        lines.append(f"- {_text(item.text)}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    lines.extend(["", "## Public interfaces", ""])
    for item in canonical.public_interfaces:
        lines.append(f"- {_code(item.name)} — {_text(item.description)}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    lines.extend(["", "## Dependencies", ""])
    for item in canonical.dependencies:
        lines.append(f"- {_code(item.target)} — {_text(item.description)}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    lines.extend(["", "## Relations", ""])
    for item in canonical.relations:
        lines.append(f"- {_text(item.predicate)} → {_text(item.target)}")
        lines.extend(_pointers(item.claim_ids, claims, evidence, "  "))
    return ("\n".join(lines) + "\n").encode("utf-8")


def compile_module_wiki(
    module: ModuleKnowledge, evidence_pack: EvidencePack
) -> bytes:
    """Compile a detailed, Claim-backed Markdown module wiki page."""

    canonical, claims, evidence = _context(module, evidence_pack)
    branch = canonical.scope.branch or "(detached)"
    lines = [
        f"# {_text(canonical.title)}",
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
        _text(canonical.summary.text),
        "",
        *_pointers(canonical.summary.claim_ids, claims, evidence),
        "",
        "## Responsibilities",
        "",
    ]
    for item in canonical.responsibilities:
        lines.extend(
            [
                f"### {_text(item.text)}",
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
                _text(item.description),
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
                _text(item.description),
                "",
                *_pointers(item.claim_ids, claims, evidence),
                "",
            ]
        )
    lines.extend(["## Relations", ""])
    for item in canonical.relations:
        lines.extend(
            [
                f"### {_text(item.predicate)} → {_text(item.target)}",
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
                _text(claim.statement),
                "",
                f"- Evidence: {citations}",
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


__all__ = ["compile_module_card", "compile_module_wiki"]
