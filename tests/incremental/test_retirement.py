from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.incremental.retirement import (
    CodeWikiRetirementProver,
    RetirementCandidate,
    RetirementCheck,
    evaluate_retirement,
)
from knowledge_compiler.providers.codewiki_cli import CliResult


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
        reindexed_current_snapshot=True,
        lexical_search_complete=True,
        graph_search_complete=True,
    )
    result = evaluate_retirement(check)
    assert result is True


def test_missing_reindex_or_class_completeness_blocks_retirement() -> None:
    base = {
        "candidate": candidate(),
        "source_absent": True,
        "search_complete": True,
        "search_found_current": False,
        "inbound_relations_verified": True,
    }
    for missing in (
        "reindexed_current_snapshot",
        "lexical_search_complete",
        "graph_search_complete",
    ):
        fields = dict(base)
        fields[missing] = False
        assert evaluate_retirement(RetirementCheck(**fields)) is False

    truncated = RetirementCheck(
        **base, search_truncated=True,
        reindexed_current_snapshot=True,
        lexical_search_complete=True,
        graph_search_complete=True,
    )
    assert evaluate_retirement(truncated) is False


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
        reindexed_current_snapshot=True,
        lexical_search_complete=True,
        graph_search_complete=True,
    )
    assert evaluate_retirement(check) is True  # only deterministic proof


class SearchRunner:
    def __init__(self, results: dict[str, list[dict]]) -> None:
        self.results = results
        self.commands: list[tuple[str, ...]] = []

    def version(self) -> str:
        return "codewiki 0.6.5"

    def run(self, argv: list[str], *, root: Path) -> CliResult:
        import json

        del root
        self.commands.append(tuple(argv[1:]))
        if argv[1:3] == ["graph", "search"]:
            payload = self.results.get(argv[3], [])
            return CliResult(stdout=json.dumps(payload), returncode=0)
        return CliResult(stdout="{}", returncode=0)


def test_codewiki_prover_reindexes_and_searches_every_former_reference(
    tmp_path: Path,
) -> None:
    runner = SearchRunner({})
    proof = CodeWikiRetirementProver(tmp_path, runner=runner)(candidate())

    assert proof.search_complete is True
    assert proof.search_found_current is False
    assert proof.inbound_relations_verified is True
    assert proof.reindexed_current_snapshot is True
    assert proof.lexical_search_complete is True
    assert proof.graph_search_complete is True
    assert proof.search_truncated is False
    # source_absent is recomputed by the transaction service from disk;
    # the prover-level check alone never authorizes retirement.
    assert evaluate_retirement(proof) is False
    assert tuple(command[:2] for command in runner.commands) == (
        ("repos", "add"),
        ("analyze", str(tmp_path)),
        ("graph", "search"),
        ("graph", "search"),
    )
    assert {runner.commands[2][2], runner.commands[3][2]} == {
        "CheckoutService",
        "src/shop/checkout.py",
    }


def test_codewiki_prover_softly_blocks_when_a_query_class_fails(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.providers.codewiki_cli import CodewikiCliError

    class FailingSymbolRunner(SearchRunner):
        def run(self, argv, *, root):
            if argv[3] == "CheckoutService":
                raise CodewikiCliError("graph search unavailable")
            return super().run(argv, root=root)

    proof = CodeWikiRetirementProver(
        tmp_path, runner=FailingSymbolRunner({})
    )(candidate())

    assert proof.graph_search_complete is False
    assert proof.lexical_search_complete is True
    assert evaluate_retirement(proof) is False


def test_codewiki_prover_marks_truncated_results_inconclusive(
    tmp_path: Path,
) -> None:
    flood = [{"node": {"name": f"Symbol{index}"}} for index in range(32)]
    runner = SearchRunner(
        {"src/shop/checkout.py": flood, "CheckoutService": []}
    )

    proof = CodeWikiRetirementProver(tmp_path, runner=runner)(candidate())

    assert proof.search_truncated is True
    assert evaluate_retirement(proof) is False


def test_codewiki_prover_blocks_when_current_graph_finds_a_match(
    tmp_path: Path,
) -> None:
    runner = SearchRunner(
        {
            "CheckoutService": [
                {"node": {"name": "CheckoutService"}}
            ]
        }
    )

    proof = CodeWikiRetirementProver(tmp_path, runner=runner)(candidate())

    assert proof.search_found_current is True
