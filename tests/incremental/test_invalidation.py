from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.contracts.knowledge import ModuleKnowledge
from knowledge_compiler.incremental.invalidation import (
    InvalidationResult,
    compute_affected,
    mark_stale,
)
from knowledge_compiler.repository.changes import ChangeSet


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/golden"


def module() -> ModuleKnowledge:
    import yaml

    return ModuleKnowledge.model_validate(
        yaml.safe_load((GOLDEN / "module.yaml").read_text(encoding="utf-8"))
    )


def test_reverse_index_finds_affected_objects() -> None:
    change_set = ChangeSet(added=(), modified=("src/shop/checkout.py",), deleted=())
    evidence_paths = {
        "module.shop.checkout": ("src/shop/checkout.py", "src/shop/inventory.py"),
    }
    affected = compute_affected(change_set, evidence_paths)
    assert "module.shop.checkout" in affected


def test_untouched_objects_stay_healthy() -> None:
    change_set = ChangeSet(added=(), modified=("docs/readme.md",), deleted=())
    evidence_paths = {"module.shop.checkout": ("src/shop/checkout.py",)}
    affected = compute_affected(change_set, evidence_paths)
    assert affected == set()


def test_provider_hints_enrich_never_replace() -> None:
    from knowledge_compiler.incremental.invalidation import merge_hints

    local_affected = {"module.a"}
    hints = {"module.b"}
    merged = merge_hints(local_affected, hints)
    assert merged == {"module.a", "module.b"}
    # Local detection is always preserved even if hints are empty.
    assert merge_hints(local_affected, set()) == local_affected


def test_mark_stale_marks_validity_and_reason() -> None:
    canonical = module()
    stale = mark_stale(canonical, reason="source-modified", evidence_path="src/shop/checkout.py")
    assert stale.validity.status == "stale"
    assert stale.validity.stale_reason == "source-modified: src/shop/checkout.py"
    # All other fields unchanged.
    assert stale.id == canonical.id
    assert stale.claims == canonical.claims


def test_mark_stale_is_idempotent() -> None:
    canonical = module()
    once = mark_stale(canonical, reason="source-modified", evidence_path="p")
    twice = mark_stale(once, reason="source-modified", evidence_path="p")
    assert twice.validity == once.validity


def test_invalidation_result_separates_stale_from_healthy() -> None:
    result = InvalidationResult(
        stale=("module.shop.checkout",),
        healthy=(),
        generation="gen-invalidation-001",
    )
    assert result.stale == ("module.shop.checkout",)
    assert result.has_stale
