from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/integration"))
sys.path.insert(0, str(ROOT / "tests/storage"))

from test_real_provider_slice import make_world  # noqa: E402


def test_final_gate_fixture_build_update_recovery_and_retrieval(
    tmp_path: Path,
) -> None:
    """One continuous fixture lifecycle: build -> update -> retrieval."""

    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.cli import _default_config
    from knowledge_compiler.incremental.updating import run_incremental_update
    from knowledge_compiler.mcp_server import serve_mcp
    from knowledge_compiler.planning.module import plan_one_module
    from knowledge_compiler.repository.inventory import (
        FileRecord,
        save_baseline,
    )
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
    )
    from knowledge_compiler.retrieval.context import retrieve_task_context

    snapshot, provider, worker, plan = make_world(tmp_path)
    object_id = plan.targets[0].target.id
    git_provider = LocalGitRepositoryProvider()

    # 1. Complete fixture build: canonical generation, compiled views,
    #    verified retrieval index, and a usable MCP surface. The fixture
    #    provider pins its own fixed snapshot commit, so the demo then
    #    refreshes the agent surface the way `knowledge compile` does to
    #    stamp the index against the real repository HEAD.
    built = run_primary_build(
        repository_root=snapshot.root,
        executor="llm",
        evidence_provider=provider,
        worker=worker,
        snapshot=snapshot,
        run_id="final-gate-001",
        planner=plan_one_module,
    )
    assert built.status == "complete"
    from knowledge_compiler.compiler.wiki import compile_repository_wiki
    from knowledge_compiler.retrieval.context import build_knowledge_index

    compile_repository_wiki(snapshot.root)
    build_knowledge_index(snapshot.root)
    manifest = yaml.safe_load(
        (snapshot.root / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["wiki_generation"] == manifest["active_generation"]
    assert (snapshot.root / ".knowledge/exports/repo-wiki.html").is_file()
    context = retrieve_task_context(snapshot.root, "checkout payment")
    assert object_id in context

    writer = io.StringIO()
    serve_mcp(
        snapshot.root,
        reader=io.StringIO(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "knowledge_get_object",
                        "arguments": {"object_id": object_id},
                    },
                }
            )
            + "\n"
        ),
        writer=writer,
    )
    tool_response = json.loads(writer.getvalue().splitlines()[-1])
    assert tool_response["result"].get("isError") is not True
    assert object_id in tool_response["result"]["content"][0]["text"]

    # 2. Incremental update after a source edit: safe invalidation marks
    #    the module stale, the selective rebuild republishes it verified,
    #    and the run ends complete with current views.
    git_provider = LocalGitRepositoryProvider()
    save_baseline(
        snapshot.root / ".knowledge/baseline/eligible-files.json",
        tuple(
            FileRecord(
                path=item.path,
                blob_id=item.blob_id,
                content_hash=item.content_hash,
                size=item.size,
                language=item.language,
            )
            for item in git_provider.inventory(snapshot.root)
            if item.supported
        ),
    )
    checkout = snapshot.root / "src/shop/checkout.py"
    checkout.write_text(
        checkout.read_text(encoding="utf-8") + "\n# changed for update\n",
        encoding="utf-8",
    )
    import subprocess

    subprocess.run(
        ["git", "-C", str(snapshot.root), "add", "src/shop/checkout.py"],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", str(snapshot.root), "commit", "-qm",
            "edit checkout for update",
        ],
        check=True,
    )

    def rebuild(**kwargs):
        return run_primary_build(
            repository_root=snapshot.root,
            executor="llm",
            evidence_provider=provider,
            worker=worker,
            snapshot=snapshot,
            run_id="final-gate-002",
            planner=plan_one_module,
            target_ids=kwargs.get("target_ids"),
            preserved_items=kwargs.get("preserved_items"),
        )

    updated = run_incremental_update(
        repository_root=snapshot.root,
        executor="llm",
        config=_default_config("zh"),
        build_runner=rebuild,
    )
    assert updated.status == "complete", updated.diagnostics
    compile_repository_wiki(snapshot.root)
    build_knowledge_index(snapshot.root)
    manifest = yaml.safe_load(
        (snapshot.root / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["wiki_generation"] == manifest["active_generation"]
    assert updated.published_object_ids == (object_id,)
    refreshed = retrieve_task_context(snapshot.root, "checkout payment")
    assert object_id in refreshed


def test_interrupted_replacement_recovers_previous_generation(
    tmp_path: Path,
) -> None:
    from test_generation_publication import _verified_inputs
    from knowledge_compiler.storage import GenerationPublisher, PublicationError

    snapshot, _provider, _worker, _plan = make_world(tmp_path)
    module, pack = _verified_inputs()
    object_id = module.id
    with_replacement = module.model_copy(
        update={"title": "Replacement title for recovery"}
    )
    GenerationPublisher(snapshot.root).publish_generation(
        "final-gate-recovery-001", ((module, pack),)
    )
    canonical_before = (
        snapshot.root / f".knowledge/objects/modules/{object_id}.yaml"
    ).read_bytes()

    def fail(point: str) -> None:
        if point == "publish.manifest.replace":
            raise OSError("injected at publish.manifest.replace")

    with pytest.raises(PublicationError, match="publish.manifest.replace"):
        GenerationPublisher(snapshot.root, fault_injector=fail).publish_generation(
            "final-gate-recovery-002", ((with_replacement, pack),)
        )

    GenerationPublisher(snapshot.root).recover()
    assert (
        snapshot.root / f".knowledge/objects/modules/{object_id}.yaml"
    ).read_bytes() == canonical_before
    manifest = yaml.safe_load(
        (snapshot.root / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["active_generation"] == "final-gate-recovery-001"
