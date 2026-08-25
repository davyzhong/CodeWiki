from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_compiler.contracts import (
    EvidenceBudget,
    EvidencePack,
    PlanTarget,
    RepositorySnapshot,
    build_snapshot_id,
)
from knowledge_compiler.providers.base import IndexStatus


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = (ROOT / "tests/fixtures/probe_repo").resolve()
NORMALIZED = ROOT / "tests/fixtures/codewiki/0.6/normalized"

REPOSITORY_ID = "codewiki-fixture/probe-shop"
COMMIT = "f207b4f37b1375a9b9bf7fae0b89361c6e39aa86"
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
        topic="checkout inventory",
        evidence_seeds=("CheckoutService", "Inventory"),
    )


def make_provider():
    from knowledge_compiler.providers.codewiki import CodeWikiEvidenceProvider
    from knowledge_compiler.providers.codewiki_cli import FixtureCodewikiRunner

    return CodeWikiEvidenceProvider(
        FixtureCodewikiRunner(NORMALIZED),
        repository_root=REPOSITORY_ROOT,
    )


def make_fake():
    from knowledge_compiler.providers.fake import FakeEvidenceProvider

    return FakeEvidenceProvider(
        fixture_dir=ROOT / "tests/fixtures/fake_provider",
        repository_root=REPOSITORY_ROOT,
    )


FAKE_REPOSITORY_ID = "fixture/probe-shop"
FAKE_COMMIT = "probe-fixture-v1"
FAKE_SNAPSHOT = build_snapshot_id(FAKE_REPOSITORY_ID, FAKE_COMMIT, False, None)


def fake_repository() -> RepositorySnapshot:
    return RepositorySnapshot.model_validate(
        {
            "repository_id": FAKE_REPOSITORY_ID,
            "snapshot_id": FAKE_SNAPSHOT,
            "root": REPOSITORY_ROOT,
            "branch": "main",
            "commit": FAKE_COMMIT,
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
    )


WORLDS = {
    "codewiki-fixture": (make_provider, repository),
    "fake": (make_fake, fake_repository),
}


@pytest.mark.parametrize("world", WORLDS)
def test_inspect_rejects_foreign_repository(world: str) -> None:
    provider, repo_factory = WORLDS[world]
    with pytest.raises(ValueError):
        provider().inspect(
            repo_factory().model_copy(
                update={"repository_id": "other/repo", "snapshot_id": None}
            )
        )


@pytest.mark.parametrize("world", WORLDS)
def test_inspect_rejects_foreign_root(world: str) -> None:
    provider, repo_factory = WORLDS[world]
    with pytest.raises(ValueError):
        provider().inspect(
            repo_factory().model_copy(update={"root": ROOT / "tests/fixtures"})
        )


@pytest.mark.parametrize("world", WORLDS)
def test_get_evidence_rejects_unknown_id(world: str) -> None:
    provider, repo_factory = WORLDS[world]
    with pytest.raises(KeyError):
        provider().get_evidence(repo_factory(), "sha256:" + "0" * 64)


def test_ensure_index_registers_and_analyzes_only() -> None:
    from knowledge_compiler.providers.codewiki import CodeWikiEvidenceProvider
    from knowledge_compiler.providers.codewiki_cli import (
        FixtureCodewikiRunner,
    )

    runner = FixtureCodewikiRunner(NORMALIZED)
    provider = CodeWikiEvidenceProvider(
        runner, repository_root=REPOSITORY_ROOT
    )
    status = provider.ensure_index(repository())

    assert isinstance(status, IndexStatus)
    assert status.repository_id == REPOSITORY_ID
    assert status.snapshot_id == SNAPSHOT_ID
    assert runner.invoked_commands[-2:] == ["repos_add", "analyze"]
    assert "update" not in runner.invoked_commands
    assert "graph_affected" not in runner.invoked_commands


def test_inspect_normalizes_scan_and_search() -> None:
    provider = make_provider()
    survey = provider.inspect(repository())

    assert survey.repository_id == REPOSITORY_ID
    assert survey.snapshot_id == SNAPSHOT_ID
    assert "src/shop/checkout.py" in survey.files
    assert "python" in survey.languages
    assert any("CheckoutService" in symbol for symbol in survey.symbols)
    assert survey.graph_communities
    assert all(isinstance(fact, tuple) for fact in survey.graph_communities)


def test_build_pack_reads_local_source_with_project_owned_ids() -> None:
    provider = make_provider()
    pack = provider.build_pack(
        repository(),
        target(),
        EvidenceBudget(max_items=4, max_characters=4000, max_tokens=512),
    )

    assert isinstance(pack, EvidencePack)
    assert pack.target.id == "module.shop.checkout"
    assert pack.evidence
    checkout = [
        item for item in pack.evidence if item.path == "src/shop/checkout.py"
    ]
    assert checkout
    item = checkout[0]
    assert item.provider == "codewiki"
    assert item.commit == COMMIT
    assert item.excerpt
    for evidence in pack.evidence:
        local = REPOSITORY_ROOT.joinpath(*Path(evidence.path).parts)
        assert local.resolve().is_relative_to(REPOSITORY_ROOT)
        assert local.is_file()
    assert pack.graph_facts
    assert any(
        fact.predicate == "calls"
        for fact in pack.graph_facts
    )


def test_build_pack_enforces_budgets_before_return() -> None:
    provider = make_provider()
    with pytest.raises(ValueError, match="budget"):
        provider.build_pack(
            repository(),
            target(),
            EvidenceBudget(max_items=1, max_characters=50, max_tokens=5),
        )


def test_build_pack_rejects_provider_path_escape() -> None:
    from knowledge_compiler.providers.codewiki import CodeWikiEvidenceProvider
    from knowledge_compiler.providers.codewiki_cli import FixtureCodewikiRunner

    runner = FixtureCodewikiRunner(NORMALIZED)
    explore = json.loads((NORMALIZED / "graph_explore.json").read_text())
    for entry in explore["json_value"]["entry_points"]:
        entry["file_path"] = "../outside.py"
    runner._responses["graph_explore"] = explore["json_value"]

    provider = CodeWikiEvidenceProvider(runner, repository_root=REPOSITORY_ROOT)
    with pytest.raises(ValueError, match="escape"):
        provider.build_pack(
            repository(),
            target(),
            EvidenceBudget(max_items=4, max_characters=4000, max_tokens=512),
        )


def test_credential_redaction_before_pack_leaves_worker() -> None:
    import shutil as shutil_module

    from knowledge_compiler.providers.codewiki import CodeWikiEvidenceProvider
    from knowledge_compiler.providers.codewiki_cli import FixtureCodewikiRunner

    secret_repo = Path(
        pytest.ensuretemp() if False else REPOSITORY_ROOT
    )
    tmp = Path(__import__("tempfile").mkdtemp())
    copied = tmp / "probe_repo"
    shutil_module.copytree(REPOSITORY_ROOT, copied)
    checkout = copied / "src/shop/checkout.py"
    original = checkout.read_text(encoding="utf-8")
    planted = original.replace(
        "raise ValueError(\"inventory reservation failed\")",
        "token = \"ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8\"\n"
        "        raise ValueError(\"inventory reservation failed\")",
    )
    checkout.write_text(planted, encoding="utf-8")

    snapshot = repository(root=copied.resolve())
    provider = CodeWikiEvidenceProvider(
        FixtureCodewikiRunner(NORMALIZED), repository_root=copied.resolve()
    )
    pack = provider.build_pack(
        snapshot,
        target(),
        EvidenceBudget(max_items=4, max_characters=8000, max_tokens=800),
    )

    joined = "\n".join(item.excerpt for item in pack.evidence)
    assert "ghp_a1B2" not in joined.replace("[REDACTED]", "")
    assert "[REDACTED]" in joined
    for item in pack.evidence:
        local = copied.joinpath(*Path(item.path).parts)
        data = local.read_bytes()
        assert data  # source still readable
        assert item.excerpt_hash != item.content_hash or b"[REDACTED]" not in data

    shutil_module.rmtree(tmp)


def test_version_gate_fail_closed() -> None:
    from knowledge_compiler.providers.codewiki_cli import (
        CodewikiCliError,
        parse_codewiki_version,
        require_supported_version,
    )

    assert parse_codewiki_version("codewiki 0.6.5") == (0, 6, 5)
    require_supported_version("codewiki 0.6.5")
    for bad in ("codewiki 0.7.0", "codewiki 0.5.2", "anything else", ""):
        with pytest.raises(CodewikiCliError):
            require_supported_version(bad)
    with pytest.raises(CodewikiCliError):
        require_supported_version(None)


def test_m5_reserved_surfaces_normalize_without_invocation() -> None:
    from knowledge_compiler.providers.codewiki import (
        normalize_affected,
        normalize_update,
    )

    update_payload = json.loads((NORMALIZED / "update.json").read_text())[
        "json_value"
    ]
    update = normalize_update(update_payload)
    assert update["mode"] == "incremental"
    assert update["status"] == "done"

    affected_payload = json.loads(
        (NORMALIZED / "graph_affected.json").read_text()
    )["json_value"]
    affected = normalize_affected(affected_payload)
    assert isinstance(affected["changed_files"], list)
    assert isinstance(affected["affected_node_ids"], list)
