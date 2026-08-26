from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from knowledge_compiler.retrieval.context import (
    ContextRetrievalError,
    UNAVAILABLE,
    build_knowledge_index,
    retrieve_task_context,
)
from knowledge_compiler.storage import GenerationPublisher


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests/fixtures/probe_repo"
sys.path.insert(0, str(ROOT / "tests/integration"))
sys.path.insert(0, str(ROOT / "tests/storage"))

from test_generation_publication import _verified_inputs  # noqa: E402
from test_typed_publication import canonicalize  # noqa: E402


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(PROBE, repo)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@e.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "T"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True
    )
    return repo


def publish_verified_world(repo: Path) -> dict[str, str]:
    module, pack = _verified_inputs()
    ids = {"module": module.id}
    items: list[tuple[object, object | None]] = [(module, pack)]
    for type_name in ("architecture", "flow", "rule", "tech-stack"):
        canonical = canonicalize(type_name).canonical
        assert canonical is not None
        ids[type_name] = canonical.id
        items.append((canonical, None))
    import json

    target = repo / ".knowledge/state/runs/manual-ctx/targets" / module.id
    target.mkdir(parents=True)
    (target / "verified.json").write_text(
        json.dumps(
            {
                "canonical": module.model_dump(mode="json"),
                "evidence_pack": pack.model_dump(mode="json"),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    GenerationPublisher(repo).publish_generation("gen-ctx-001", tuple(items))
    return ids


def test_index_contains_only_verified_objects_and_matches_stamps(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    ids = publish_verified_world(repo)

    result = build_knowledge_index(repo)

    assert result.generation == "gen-ctx-001"
    assert set(result.verified_object_ids) == set(ids.values())
    assert (repo / ".knowledge/cache/knowledge-index.sqlite3").is_file()


def test_context_requires_index_and_fails_closed_when_lagging(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    publish_verified_world(repo)

    with pytest.raises(ContextRetrievalError, match=UNAVAILABLE):
        retrieve_task_context(repo, "checkout payment")

    build_knowledge_index(repo)
    markdown = retrieve_task_context(repo, "checkout payment")
    assert "checkout" in markdown.lower()

    # A newer publication without an index rebuild must fail closed.
    module, pack = _verified_inputs()
    GenerationPublisher(repo).publish_generation(
        "gen-ctx-002", ((module, pack),)
    )
    with pytest.raises(ContextRetrievalError, match=UNAVAILABLE):
        retrieve_task_context(repo, "checkout payment")


def test_context_fails_closed_on_uncommitted_changes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    publish_verified_world(repo)
    build_knowledge_index(repo)

    (repo / "src/shop/checkout.py").write_text(
        "# dirty working tree\n", encoding="utf-8"
    )
    with pytest.raises(ContextRetrievalError, match="uncommitted"):
        retrieve_task_context(repo, "checkout payment")


def test_context_ranks_matches_and_applies_budget(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    ids = publish_verified_world(repo)
    build_knowledge_index(repo)

    markdown = retrieve_task_context(repo, ids["module"], budget=6000)
    assert ids["module"] in markdown
    assert "Key claims:" in markdown
    assert "Evidence pointers:" in markdown

    tight = retrieve_task_context(repo, ids["module"], budget=1)
    assert len(tight) < len(markdown)


def test_context_is_deterministic(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    publish_verified_world(repo)
    build_knowledge_index(repo)

    first = retrieve_task_context(repo, "inventory reservation")
    second = retrieve_task_context(repo, "inventory reservation")
    assert first == second


def test_human_overlay_joins_retrieval_with_attribution(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    ids = publish_verified_world(repo)
    overlay = repo / ".knowledge/human/modules" / f"{ids['module']}.yaml"
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {ids['module']}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections: []\n"
        "notes:\n"
        f"  - id: {ids['module']}.note.ops\n"
        "    text: Cash payments need operator signoff.\n"
        "    basis: incident review\n",
        encoding="utf-8",
    )
    build_knowledge_index(repo)

    markdown = retrieve_task_context(repo, "operator signoff")

    assert "source: human" in markdown
    assert "Cash payments need operator signoff." in markdown


def test_include_stale_is_diagnostic_only(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    ids = publish_verified_world(repo)
    build_knowledge_index(repo)
    from knowledge_compiler.contracts.knowledge import ModuleKnowledge

    module, pack = _verified_inputs()
    data = module.model_dump(mode="json")
    data["validity"] = {
        "status": "stale",
        "verified_commit": module.validity.verified_commit,
        "stale_reason": "evidence changed",
    }
    stale = ModuleKnowledge.model_validate(data)
    GenerationPublisher(repo).publish_generation(
        "gen-ctx-stale", ((stale, pack),)
    )
    build_knowledge_index(repo)

    markdown = retrieve_task_context(
        repo, "checkout payment", include_stale=True
    )

    assert "Diagnostic stale view" in markdown
    assert ids["module"] in markdown
    assert "evidence changed" in markdown
    plain = retrieve_task_context(repo, "checkout payment")
    assert "evidence changed" not in plain
