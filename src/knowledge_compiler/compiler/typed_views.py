from __future__ import annotations

from knowledge_compiler.compiler.markdown import _claim_evidence, _code, _text
from knowledge_compiler.compiler.human import (
    render_overlay_field,
    render_overlay_notes,
)
from knowledge_compiler.compiler.yaml import CompilerInputError
from knowledge_compiler.contracts.human import HumanOverlay


def compile_typed_wiki(
    model: object,
    overlay: HumanOverlay | None = None,
    *,
    pack: object | None = None,
    web_url: str | None = None,
) -> bytes:
    """Render a minimal deterministic wiki page for any typed object.

    The complete human Wiki lands in M7; this page guarantees every
    published generation carries a wiki view derived only from the
    canonical payload. When an Evidence Pack is supplied, every claim
    renders its citations (with permalinks when ``web_url`` is set).
    """

    summary = getattr(model, "summary", None)
    title = getattr(model, "title", None)
    identifier = getattr(model, "id")
    validity = getattr(model, "validity", None)
    if title is None or identifier is None or summary is None:
        raise CompilerInputError("typed wiki requires a canonical payload")

    claims_by_id = {claim.id: claim for claim in getattr(model, "claims", ())}
    evidence_by_id = (
        {item.id: item for item in pack.evidence} if pack is not None else {}
    )

    def _evidence_lines(claim_ids: tuple[str, ...], indent: str = "") -> list[str]:
        if not pack or not claim_ids or not evidence_by_id:
            return []
        resolvable = [
            claim_id
            for claim_id in claim_ids
            if claim_id in claims_by_id
            and any(
                evidence_id in evidence_by_id
                for evidence_id in claims_by_id[claim_id].evidence_ids
            )
        ]
        if not resolvable:
            return []
        _claims_used, citations = _claim_evidence(
            resolvable, claims_by_id, evidence_by_id, web_url=web_url
        )
        return [f"{indent}- Evidence: {citations}"]

    lines = [
        f"# {_text(str(title))}",
        "",
        f"{_code(str(identifier))}"
        + (
            f" · verified at {_code(validity.verified_commit)}"
            if validity is not None
            else ""
        ),
        "",
    ]
    lines.extend(
        render_overlay_field(
            [
                _text(str(summary.text)),
                "",
                f"- Claims: {_code(', '.join(summary.claim_ids))}",
                *_evidence_lines(summary.claim_ids),
            ],
            overlay=overlay,
            field="summary",
            escape=_text,
        )
    )
    claims = getattr(model, "claims", ())
    if claims:
        lines.extend(["", "## Verified claims", ""])
        for claim in claims:
            lines.extend(
                [
                    f"### {_code(claim.id)}",
                    "",
                    _text(claim.statement),
                    "",
                    *_evidence_lines((claim.id,)),
                ]
            )
    lines.extend(render_overlay_notes(overlay, escape=_text))
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = ["compile_typed_wiki"]
