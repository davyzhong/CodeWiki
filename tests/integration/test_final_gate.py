from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests/fixtures/probe_repo"
NORMALIZED = ROOT / "tests/fixtures/codewiki/0.6/normalized"
sys.path.insert(0, str(ROOT / "tests/integration"))
sys.path.insert(0, str(ROOT / "tests/storage"))

from knowledge_compiler.providers.codewiki_cli import (  # noqa: E402
    FixtureCodewikiRunner,
)


class LiveCommitScanner(FixtureCodewikiRunner):
    """Fixture runner whose scan reflects the live repository HEAD.

    The captured scan pins one recorded commit; a static echo would let
    a fixture snapshot contradict reality. Returning the current HEAD
    mirrors what the public CodeWiki CLI reports for a live repository
    and keeps every downstream gate anchored to Git truth.
    """

    def run(self, argv, *, root):  # type: ignore[override]
        tokens = list(argv)[1:]
        if len(tokens) >= 2 and tokens[0] == "repos" and tokens[1] == "scan":
            result = super().run(argv, root=root)
            try:
                payload = json.loads(result.stdout)
            except ValueError:
                return result
            head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            repo_section = payload.get("repo")
            if isinstance(repo_section, dict):
                repo_section["commit_hash"] = head
            return type(result)(
                stdout=json.dumps(payload),
                returncode=result.returncode,
            )
        return super().run(argv, root=root)


def make_repository(tmp_path: Path) -> Path:
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
    # A normalizable remote keeps the derived repository id (and every
    # object id built from it) inside the documented ID grammar.
    subprocess.run(
        [
            "git", "-C", str(repo), "remote", "add", "origin",
            "https://github.com/fixture/probe-shop.git",
        ],
        check=True,
    )
    return repo


def make_world_against_reality(tmp_path: Path):
    """A five-type-capable world whose every layer shares Git truth."""

    from knowledge_compiler.contracts.planning import PlanRequest
    from knowledge_compiler.planning.module import (
        plan_one_module,
    )
    from knowledge_compiler.providers.codewiki import (
        CodeWikiEvidenceProvider,
    )

    repo = make_repository(tmp_path / "world")
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
    )

    snapshot = LocalGitRepositoryProvider().resolve(repo)
    provider = CodeWikiEvidenceProvider(
        LiveCommitScanner(NORMALIZED), repository_root=snapshot.root
    )
    survey = provider.inspect(snapshot)
    request = PlanRequest.model_validate(
        {
            "run_id": "final-gate-run-001",
            "repository_id": snapshot.repository_id,
            "snapshot_id": snapshot.snapshot_id,
            "attempt": 1,
            "idempotency_key": (
                f"final-gate-run-001:plan:1:{snapshot.snapshot_id}"
            ),
        }
    )
    plan = plan_one_module(request, survey)
    object_id = plan.targets[0].target.id

    from test_real_provider_slice import StubRealWorker

    worker = StubRealWorker(repo, object_id, "final-gate-run-001")

    class World:
        pass

    world = World()
    world.root = repo
    world.snapshot = snapshot
    world.provider = provider
    world.worker = worker
    world.plan = plan
    world.object_id = object_id
    world.git = LocalGitRepositoryProvider()
    return world


def test_final_gate_fixture_build_update_recovery_and_retrieval(
    tmp_path: Path,
) -> None:
    """One continuous fixture lifecycle: build -> update -> exact gates."""

    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.cli import _default_config
    from knowledge_compiler.incremental.updating import run_incremental_update
    from knowledge_compiler.mcp_server import serve_mcp
    from knowledge_compiler.planning.module import plan_one_module
    from knowledge_compiler.retrieval.context import (
        ContextRetrievalError,
        UNAVAILABLE,
        retrieve_task_context,
    )

    world = make_world_against_reality(tmp_path)
    repository_root = world.snapshot.root

    def fresh_snapshot():
        return world.git.resolve(repository_root)

    # 1. Complete fixture build against the resolved repository; views,
    #    index, tracked plan state, and MCP all emerge from production
    #    paths without any post-hoc refresh injection.
    built = run_primary_build(
        repository_root=repository_root,
        executor="llm",
        evidence_provider=world.provider,
        worker=world.worker,
        snapshot=fresh_snapshot(),
        run_id="final-gate-001",
        planner=plan_one_module,
    )
    assert built.status == "complete", built.diagnostics

    context = retrieve_task_context(repository_root, "checkout payment")
    assert world.object_id in context

    writer = io.StringIO()
    serve_mcp(
        repository_root,
        reader=io.StringIO(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "knowledge_get_object",
                        "arguments": {"object_id": world.object_id},
                    },
                }
            )
            + "\n"
        ),
        writer=writer,
    )
    tool_response = json.loads(writer.getvalue().splitlines()[-1])
    assert tool_response["result"].get("isError") is not True
    assert world.object_id in tool_response["result"]["content"][0]["text"]

    # 2. Committed source change -> incremental update rebuilds the
    #    affected target and the exact new snapshot passes every gate.
    from knowledge_compiler.repository.inventory import (
        FileRecord,
        save_baseline,
    )

    save_baseline(
        repository_root / ".knowledge/baseline/eligible-files.json",
        tuple(
            FileRecord(
                path=item.path,
                blob_id=item.blob_id,
                content_hash=item.content_hash,
                size=item.size,
                language=item.language,
            )
            for item in world.git.inventory(repository_root)
            if item.supported
        ),
    )
    checkout = repository_root / "src/shop/checkout.py"
    checkout.write_text(
        checkout.read_text(encoding="utf-8") + "\n# changed for update\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repository_root), "add", "src/shop/checkout.py"],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", str(repository_root), "commit", "-qm",
            "edit checkout for update",
        ],
        check=True,
    )

    def rebuild(**kwargs):
        return run_primary_build(
            repository_root=repository_root,
            executor="llm",
            evidence_provider=world.provider,
            worker=world.worker,
            snapshot=fresh_snapshot(),
            run_id="final-gate-002",
            planner=plan_one_module,
            target_ids=kwargs.get("target_ids"),
            preserved_items=kwargs.get("preserved_items"),
        )

    updated = run_incremental_update(
        repository_root=repository_root,
        executor="llm",
        config=_default_config("zh"),
        build_runner=rebuild,
    )
    assert updated.status == "complete", updated.diagnostics
    assert updated.published_object_ids == (world.object_id,)
    refreshed = retrieve_task_context(repository_root, "checkout payment")
    assert world.object_id in refreshed
    manifest = yaml.safe_load(
        (repository_root / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["wiki_generation"] == manifest["active_generation"]

    # 3. An uncommitted byte change breaks exact snapshot identity; the
    #    gate must fail closed until the tree matches the indexed truth.
    checkout.write_text(
        checkout.read_text(encoding="utf-8") + "\n# stray local edit\n",
        encoding="utf-8",
    )
    with pytest.raises(ContextRetrievalError, match=UNAVAILABLE):
        retrieve_task_context(repository_root, "checkout payment")


def test_interrupted_replacement_recovers_previous_generation(
    tmp_path: Path,
) -> None:
    from test_generation_publication import _verified_inputs
    from knowledge_compiler.storage import GenerationPublisher, PublicationError

    repo = make_repository(tmp_path / "publisher-world")
    module, pack = _verified_inputs()
    object_id = module.id
    with_replacement = module.model_copy(
        update={"title": "Replacement title for recovery"}
    )
    GenerationPublisher(repo).publish_generation(
        "final-gate-recovery-001", ((module, pack),)
    )
    canonical_before = (
        repo / f".knowledge/objects/modules/{object_id}.yaml"
    ).read_bytes()

    def fail(point: str) -> None:
        if point == "publish.manifest.replace":
            raise OSError("injected at publish.manifest.replace")

    with pytest.raises(PublicationError, match="publish.manifest.replace"):
        GenerationPublisher(repo, fault_injector=fail).publish_generation(
            "final-gate-recovery-002", ((with_replacement, pack),)
        )

    GenerationPublisher(repo).recover()
    assert (
        repo / f".knowledge/objects/modules/{object_id}.yaml"
    ).read_bytes() == canonical_before
    manifest = yaml.safe_load((repo / ".knowledge/manifest.yaml").read_bytes())
    assert manifest["active_generation"] == "final-gate-recovery-001"
