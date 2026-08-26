from __future__ import annotations

from knowledge_compiler.compiler.markdown import _code, _text
from knowledge_compiler.compiler.human import (
    render_overlay_field,
    render_overlay_notes,
)
from knowledge_compiler.compiler.yaml import CompilerInputError
from knowledge_compiler.contracts.human import HumanOverlay


def compile_typed_wiki(
    model: object, overlay: HumanOverlay | None = None
) -> bytes:
    """Render a minimal deterministic wiki page for any typed object.

    The complete human Wiki lands in M7; this page guarantees every
    published generation carries a wiki view derived only from the
    canonical payload.
    """

    summary = getattr(model, "summary", None)
    title = getattr(model, "title", None)
    identifier = getattr(model, "id", None)
    validity = getattr(model, "validity", None)
    if title is None or identifier is None or summary is None:
        raise CompilerInputError("typed wiki requires a canonical payload")
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
                ]
            )
    lines.extend(render_overlay_notes(overlay, escape=_text))
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = ["compile_typed_wiki"]
