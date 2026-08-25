from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.incremental.retirement import (
    RetirementCandidate,
    RetirementCheck,
    evaluate_retirement,
)


def candidate(*, source_absent: bool = True) -> RetirementCandidate:
    return RetirementCandidate(
        object_id="module.shop.checkout",
        evidence_paths=("src/shop/checkout.py",),
        former_symbols=("CheckoutService",),
        inbound_relations=(),
    )


def test_all_proofs_pass_authorizes_retirement() -> None:
    check = RetirementCheck(
        candidate=candidate(),
        source_absent=True,
        search_complete=True,
        search_found_current=False,
        inbound_relations_verified=True,
    )
    result = evaluate_retirement(check)
    assert result is True


def test_source_still_present_blocks_retirement() -> None:
    check = RetirementCheck(
        candidate=candidate(),
        source_absent=False,
        search_complete=True,
        search_found_current=False,
        inbound_relations_verified=True,
    )
    assert evaluate_retirement(check) is False


def test_inconclusive_search_keeps_stale() -> None:
    check = RetirementCheck(
        candidate=candidate(),
        source_absent=True,
        search_complete=False,
        search_found_current=False,
        inbound_relations_verified=True,
    )
    assert evaluate_retirement(check) is False


def test_current_candidate_found_blocks_retirement() -> None:
    check = RetirementCheck(
        candidate=candidate(),
        source_absent=True,
        search_complete=True,
        search_found_current=True,
        inbound_relations_verified=True,
    )
    assert evaluate_retirement(check) is False


def test_unverified_inbound_relations_block_retirement() -> None:
    check = RetirementCheck(
        candidate=candidate(),
        source_absent=True,
        search_complete=True,
        search_found_current=False,
        inbound_relations_verified=False,
    )
    assert evaluate_retirement(check) is False


def test_model_output_never_authorizes() -> None:
    # The check record carries only deterministic fields; there is no
    # model-output pathway into evaluate_retirement by construction.
    check = RetirementCheck(
        candidate=candidate(),
        source_absent=True,
        search_complete=True,
        search_found_current=False,
        inbound_relations_verified=True,
    )
    assert evaluate_retirement(check) is True  # only deterministic proof
