from __future__ import annotations

import sys
from pathlib import Path

from knowledge_compiler.human.conflicts import split_overlay_conflicts
from knowledge_compiler.storage import GenerationPublisher


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/integration"))

from test_typed_publication import canonicalize  # noqa: E402


def write_overlay(root: Path, object_id: str, mode: str) -> bytes:
    path = root / ".knowledge/human/architecture" / f"{object_id}.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {object_id}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections:\n"
        "  - field: summary\n"
        f"    mode: {mode}\n"
        "    text: Human architecture summary.\n"
        "    basis: architecture review\n"
        "notes: []\n",
        encoding="utf-8",
    )
    return path.read_bytes()


def changed_summary_evidence(canonical):
    summary_claim_id = canonical.summary.claim_ids[0]
    claims = []
    for claim in canonical.claims:
        if claim.id == summary_claim_id:
            verification = claim.verification.model_copy(
                update={"excerpt_hashes": ("sha256:" + "9" * 64,)}
            )
            claim = claim.model_copy(update={"verification": verification})
        claims.append(claim)
    return canonical.model_copy(update={"claims": tuple(claims)})


def test_changed_evidence_under_override_conflicts_and_preserves_old(
    tmp_path: Path,
) -> None:
    current = canonicalize("architecture").canonical
    assert current is not None
    GenerationPublisher(tmp_path).publish_generation(
        "gen-before-conflict", ((current, None),)
    )
    overlay_bytes = write_overlay(tmp_path, current.id, "override")

    split = split_overlay_conflicts(
        tmp_path, ((changed_summary_evidence(current), None),)
    )

    assert split.accepted == ()
    assert tuple(item[0].id for item in split.preserved) == (current.id,)
    assert split.conflicts == {current.id: ("summary",)}
    assert (
        tmp_path
        / ".knowledge/human/architecture"
        / f"{current.id}.yaml"
    ).read_bytes() == overlay_bytes


def test_supplement_never_blocks_regeneration(tmp_path: Path) -> None:
    current = canonicalize("architecture").canonical
    assert current is not None
    GenerationPublisher(tmp_path).publish_generation(
        "gen-before-supplement", ((current, None),)
    )
    write_overlay(tmp_path, current.id, "supplement")
    changed = changed_summary_evidence(current)

    split = split_overlay_conflicts(tmp_path, ((changed, None),))

    assert tuple(item[0].id for item in split.accepted) == (current.id,)
    assert split.preserved == ()
    assert split.conflicts == {}
