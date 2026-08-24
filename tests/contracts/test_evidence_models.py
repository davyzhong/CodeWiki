from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_compiler.contracts.evidence import (
    EvidenceItem,
    EvidencePack,
    GraphFact,
    RepositorySurvey,
    build_evidence_id,
)
from knowledge_compiler.contracts.repository import (
    EvidenceBudget,
    PlanTarget,
    RepositorySnapshot,
    build_snapshot_id,
)


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def make_repository(**overrides: object) -> RepositorySnapshot:
    values: dict[str, object] = {
        "repository_id": "仓库/shop",
        "root": Path("/work/shop"),
        "branch": "main",
        "commit": "abc123",
        "dirty": False,
        "working_tree_hash": None,
        "eligible_files": ["src/shop/checkout.py"],
    }
    values.update(overrides)
    values.setdefault(
        "snapshot_id",
        build_snapshot_id(
            repository_id=str(values["repository_id"]),
            commit=str(values["commit"]),
            dirty=bool(values["dirty"]),
            working_tree_hash=values["working_tree_hash"],  # type: ignore[arg-type]
        ),
    )
    return RepositorySnapshot(**values)  # type: ignore[arg-type]


def make_target() -> PlanTarget:
    return PlanTarget(
        id="module.shop.checkout",
        topic="Shop checkout",
        evidence_seeds=["CheckoutService"],
    )


def make_item(repository: RepositorySnapshot, **overrides: object) -> EvidenceItem:
    values: dict[str, object] = {
        "provider": "fake",
        "path": "src/shop/checkout.py",
        "symbol": "CheckoutService.checkout",
        "start_line": 10,
        "end_line": 12,
        "commit": repository.commit,
        "content_hash": HASH_A,
        "excerpt_hash": HASH_B,
        "excerpt": "def checkout():\n    return '[REDACTED]'\n",
        "relationship": "defines",
    }
    values.update(overrides)
    values.setdefault(
        "id",
        build_evidence_id(
            repository_id=repository.repository_id,
            snapshot_id=repository.snapshot_id,
            path=str(values["path"]),
            symbol=values["symbol"],  # type: ignore[arg-type]
            start_line=int(values["start_line"]),
            end_line=int(values["end_line"]),
            content_hash=str(values["content_hash"]),
        ),
    )
    return EvidenceItem(**values)  # type: ignore[arg-type]


def make_pack(
    *,
    repository: RepositorySnapshot | None = None,
    evidence: list[EvidenceItem] | None = None,
    budget: EvidenceBudget | None = None,
    token_counter=None,
) -> EvidencePack:
    repository = repository or make_repository()
    evidence = evidence if evidence is not None else [make_item(repository)]
    payload = {
        "repository": repository,
        "target": make_target(),
        "budget": budget or EvidenceBudget(max_items=2, max_characters=100, max_tokens=20),
        "evidence": evidence,
        "graph_facts": [
            GraphFact(
                source="CheckoutService.checkout",
                predicate="calls",
                target="Inventory.reserve",
                confidence="deterministic",
                provenance={"provider": "fake"},
            )
        ],
    }
    return EvidencePack.model_validate(
        payload,
        context={"token_counter": token_counter} if token_counter else None,
    )


def test_repository_snapshot_id_uses_canonical_utf8_json() -> None:
    expected = canonical_hash(["仓库/shop", "abc123", True, HASH_A])

    assert build_snapshot_id("仓库/shop", "abc123", True, HASH_A) == expected
    assert make_repository(dirty=True, working_tree_hash=HASH_A).snapshot_id == expected


def test_repository_snapshot_rejects_mismatched_id_and_relative_root() -> None:
    with pytest.raises(ValidationError, match="snapshot_id"):
        make_repository(snapshot_id="sha256:" + "f" * 64)

    with pytest.raises(ValidationError, match="absolute"):
        make_repository(root=Path("relative/shop"))


def test_plan_target_and_positive_evidence_budget_contracts() -> None:
    target = make_target()
    assert target.type == "module"

    with pytest.raises(ValidationError):
        PlanTarget(id="flow.shop.checkout", type="flow", topic="checkout", evidence_seeds=[])

    for field in ("max_items", "max_characters", "max_tokens"):
        values = {"max_items": 1, "max_characters": 1, "max_tokens": 1, field: 0}
        with pytest.raises(ValidationError):
            EvidenceBudget(**values)


def test_evidence_item_round_trips_with_fixed_source_contract() -> None:
    item = make_item(make_repository())

    restored = EvidenceItem.model_validate_json(item.model_dump_json())

    assert restored == item
    assert restored.kind == "source"
    assert restored.strength == "direct"
    assert "[REDACTED]" in restored.excerpt


def test_evidence_id_uses_normalized_posix_path_and_canonical_json() -> None:
    repository = make_repository()
    expected = canonical_hash(
        [
            repository.repository_id,
            repository.snapshot_id,
            "src/shop/checkout.py",
            "CheckoutService.checkout",
            10,
            12,
            HASH_A,
        ]
    )

    assert (
        build_evidence_id(
            repository.repository_id,
            repository.snapshot_id,
            "src/shop/./checkout.py",
            "CheckoutService.checkout",
            10,
            12,
            HASH_A,
        )
        == expected
    )


@pytest.mark.parametrize("path", ["/src/shop.py", "../shop.py", "src/../../shop.py"])
def test_evidence_rejects_absolute_or_traversing_paths(path: str) -> None:
    with pytest.raises((ValueError, ValidationError), match="path"):
        make_item(make_repository(), path=path)


def test_evidence_rejects_invalid_ranges_and_hashes() -> None:
    repository = make_repository()
    with pytest.raises(ValidationError):
        make_item(repository, start_line=0)
    with pytest.raises(ValidationError, match="end_line"):
        make_item(repository, start_line=5, end_line=4)
    for field in ("id", "content_hash", "excerpt_hash"):
        with pytest.raises(ValidationError):
            make_item(repository, **{field: "sha256:not-a-hash"})


def test_repository_survey_round_trips_project_owned_facts() -> None:
    repository = make_repository()
    survey = RepositorySurvey(
        repository_id=repository.repository_id,
        snapshot_id=repository.snapshot_id,
        files=["src/shop/checkout.py"],
        languages=["Python"],
        symbols=["CheckoutService.checkout"],
        graph_communities=[["CheckoutService.checkout", "Inventory.reserve"]],
        configuration_facts={"python": "3.12"},
    )
    assert RepositorySurvey.model_validate_json(survey.model_dump_json()) == survey


def test_evidence_pack_round_trips_and_binds_identity() -> None:
    pack = make_pack(token_counter=lambda text: len(text.split()))

    assert EvidencePack.model_validate(pack.model_dump()) == pack
    assert pack.contract_version == "0.1"

    other_repository = make_repository(repository_id="other")
    with pytest.raises(ValidationError, match="Evidence ID"):
        make_pack(repository=other_repository, evidence=[make_item(make_repository())])

    mismatched_snapshot = make_repository(commit="def456")
    payload = pack.model_dump()
    payload["repository"] = mismatched_snapshot
    with pytest.raises(ValidationError, match="snapshot"):
        EvidencePack.model_validate(payload)


def test_evidence_pack_rejects_duplicate_or_incorrectly_derived_ids() -> None:
    repository = make_repository()
    item = make_item(repository)
    with pytest.raises(ValidationError, match="duplicate"):
        make_pack(repository=repository, evidence=[item, item])

    wrong = item.model_copy(update={"id": "sha256:" + "f" * 64})
    with pytest.raises(ValidationError, match="Evidence ID"):
        make_pack(repository=repository, evidence=[wrong])


@pytest.mark.parametrize(
    ("budget", "token_counter", "message"),
    [
        (EvidenceBudget(max_items=1, max_characters=100, max_tokens=100), None, "item"),
        (EvidenceBudget(max_items=2, max_characters=3, max_tokens=100), None, "character"),
        (EvidenceBudget(max_items=2, max_characters=100, max_tokens=3), lambda _: 4, "token"),
    ],
)
def test_evidence_pack_rejects_budget_overflow(
    budget: EvidenceBudget, token_counter, message: str
) -> None:
    repository = make_repository()
    evidence = [make_item(repository)]
    if message == "item":
        evidence.append(make_item(repository, symbol="other", start_line=20, end_line=21))

    with pytest.raises(ValidationError, match=message):
        make_pack(
            repository=repository,
            evidence=evidence,
            budget=budget,
            token_counter=token_counter,
        )
