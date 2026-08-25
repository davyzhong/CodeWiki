from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_compiler.contracts import (
    EvidenceBudget,
    EvidencePack,
    PlanTarget,
    RepositorySnapshot,
    build_snapshot_id,
)
from knowledge_compiler.providers import (
    EvidenceProvider,
    FakeEvidenceProvider,
    IndexStatus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "tests/fixtures/fake_provider"
REPOSITORY_ROOT = (PROJECT_ROOT / "tests/fixtures/probe_repo").resolve()
REPOSITORY_ID = "fixture/probe-shop"
COMMIT = "probe-fixture-v1"
SNAPSHOT_ID = build_snapshot_id(REPOSITORY_ID, COMMIT, False, None)


def repository(**overrides: object) -> RepositorySnapshot:
    values: dict[str, object] = {
        "repository_id": REPOSITORY_ID,
        "snapshot_id": SNAPSHOT_ID,
        "root": REPOSITORY_ROOT,
        "branch": "main",
        "commit": COMMIT,
        "dirty": False,
        "working_tree_hash": None,
        "eligible_files": (
            "pyproject.toml",
            "src/shop/__init__.py",
            "src/shop/api.py",
            "src/shop/checkout.py",
            "src/shop/inventory.py",
        ),
    }
    values.update(overrides)
    return RepositorySnapshot.model_validate(values)


def target() -> PlanTarget:
    return PlanTarget(
        id="module.shop.checkout",
        topic="CheckoutService",
        evidence_seeds=("CheckoutService", "Inventory.reserve"),
    )


def budget() -> EvidenceBudget:
    return EvidenceBudget(max_items=2, max_characters=800, max_tokens=100)


def provider(
    fixture_dir: Path = FIXTURE_DIR,
    repository_root: Path = REPOSITORY_ROOT,
) -> FakeEvidenceProvider:
    return FakeEvidenceProvider(
        fixture_dir=fixture_dir,
        repository_root=repository_root,
    )


def copy_fixtures(tmp_path: Path) -> Path:
    destination = tmp_path / "fake_provider"
    shutil.copytree(FIXTURE_DIR, destination)
    return destination


def rewrite_json(path: Path, edit) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    edit(payload)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_fake_provider_contract_calls_all_four_methods() -> None:
    fake = provider()
    repo = repository()

    assert isinstance(fake, EvidenceProvider)
    survey = fake.inspect(repo)
    status = fake.ensure_index(repo)
    pack = fake.build_pack(repo, target(), budget())

    assert survey.repository_id == repo.repository_id
    assert survey.snapshot_id == repo.snapshot_id
    assert status == IndexStatus(
        repository_id=repo.repository_id,
        snapshot_id=repo.snapshot_id,
        state="ready",
        changed=False,
    )
    assert pack.repository == repo
    assert pack.target == target()
    assert pack.budget == budget()
    assert {
        (item.path, item.symbol, item.start_line, item.end_line)
        for item in pack.evidence
    } == {
        ("src/shop/checkout.py", "CheckoutService", 4, 11),
        ("src/shop/inventory.py", "Inventory.reserve", 1, 3),
    }
    assert all(not Path(item.path).is_absolute() for item in pack.evidence)
    assert all(item.provider == "fake-codewiki-0.6.5" for item in pack.evidence)
    assert all("[REDACTED]" in item.excerpt for item in pack.evidence)
    assert tuple(fake.get_evidence(repo, item.id) for item in pack.evidence) == pack.evidence


def test_fake_provider_rejects_repository_and_snapshot_mismatch() -> None:
    fake = provider()

    with pytest.raises(ValueError, match="repository identity mismatch"):
        fake.inspect(
            repository(
                repository_id="fixture/other",
                snapshot_id=build_snapshot_id(
                    "fixture/other", COMMIT, False, None
                ),
            )
        )

    other_commit = "probe-fixture-v2"
    with pytest.raises(ValueError, match="snapshot mismatch"):
        fake.ensure_index(
            repository(
                commit=other_commit,
                snapshot_id=build_snapshot_id(
                    REPOSITORY_ID, other_commit, False, None
                ),
            )
        )

    with pytest.raises(ValueError, match="repository root mismatch"):
        fake.build_pack(
            repository(root=REPOSITORY_ROOT.parent), target(), budget()
        )


def test_fake_provider_rejects_target_and_budget_mismatch() -> None:
    fake = provider()
    repo = repository()

    with pytest.raises(ValueError, match="target mismatch"):
        fake.build_pack(
            repo,
            PlanTarget(id="module.shop.inventory", topic="Inventory"),
            budget(),
        )

    with pytest.raises(ValueError, match="budget mismatch"):
        fake.build_pack(
            repo,
            target(),
            EvidenceBudget(max_items=1, max_characters=800, max_tokens=100),
        )


def test_fake_provider_rejects_unknown_evidence_id() -> None:
    with pytest.raises(KeyError, match="unknown Evidence ID"):
        provider().get_evidence(repository(), "sha256:" + "f" * 64)


def test_fake_provider_rejects_malformed_json_and_schema(tmp_path: Path) -> None:
    fixture_dir = copy_fixtures(tmp_path)
    (fixture_dir / "survey.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid fixture JSON"):
        provider(fixture_dir)

    fixture_dir = copy_fixtures(tmp_path / "second")
    rewrite_json(
        fixture_dir / "survey.json",
        lambda payload: payload.__setitem__("unexpected", True),
    )
    with pytest.raises(ValidationError, match="unexpected"):
        provider(fixture_dir)


def test_fake_provider_rejects_fixture_budget_overflow(tmp_path: Path) -> None:
    fixture_dir = copy_fixtures(tmp_path)
    rewrite_json(
        fixture_dir / "evidence-pack.json",
        lambda payload: payload["budget"].__setitem__("max_items", 1),
    )

    with pytest.raises(ValidationError, match="item budget exceeded"):
        provider(fixture_dir)


def test_fake_provider_rejects_fixture_paths_escaping_bound_root(
    tmp_path: Path,
) -> None:
    fixture_dir = copy_fixtures(tmp_path)
    rewrite_json(
        fixture_dir / "evidence-pack.json",
        lambda payload: payload["evidence"][0].__setitem__(
            "path", "../outside.py"
        ),
    )

    with pytest.raises(ValidationError, match="path"):
        provider(fixture_dir)


def test_fake_provider_preserves_immutability_and_revalidates_inputs() -> None:
    fake = provider()
    repo = repository()
    survey = fake.inspect(repo)
    pack = fake.build_pack(repo, target(), budget())

    with pytest.raises(ValidationError, match="frozen"):
        survey.files = ()
    with pytest.raises(ValidationError, match="frozen"):
        pack.evidence[0].excerpt = "changed"

    object.__setattr__(repo, "snapshot_id", "sha256:" + "f" * 64)
    with pytest.raises(ValidationError, match="snapshot_id"):
        fake.inspect(repo)


def test_fixture_is_portable_and_contains_no_secret_or_absolute_path() -> None:
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    )

    assert str(PROJECT_ROOT) not in serialized
    assert "inventory reservation failed" not in serialized
    assert '"order-created"' not in serialized
    assert '"root": "."' in serialized


def test_build_pack_returns_a_fresh_revalidated_project_dto() -> None:
    fake = provider()
    first = fake.build_pack(repository(), target(), budget())
    second = fake.build_pack(repository(), target(), budget())

    assert isinstance(first, EvidencePack)
    assert first == second
    assert first is not second
