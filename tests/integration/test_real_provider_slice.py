from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts.repository import (
    RepositorySnapshot,
    build_snapshot_id,
)


ROOT = Path(__file__).resolve().parents[2]
NORMALIZED = ROOT / "tests/fixtures/codewiki/0.6/normalized"
FIXTURES = ROOT / "tests/fixtures/fake_provider"
PROBE = ROOT / "tests/fixtures/probe_repo"

REPOSITORY_ID = "codewiki-fixture/probe-shop"
COMMIT = "f207b4f37b1375a9b9bf7fae0b89361c6e39aa86"
SNAPSHOT_ID = build_snapshot_id(REPOSITORY_ID, COMMIT, False, None)


class StubRealWorker:
    """Deterministic semantic worker reusing the captured fixture drafts."""

    def __init__(self, repository_root: Path, target_id: str, run_id: str) -> None:
        self._root = repository_root
        self._target_id = target_id
        self._run_id = run_id
        self.planner_output: object = None

    def extract(self, request):
        from knowledge_compiler.contracts.knowledge import ExtractionResult

        payload = json.loads(
            (FIXTURES / "module-extraction.json").read_text(encoding="utf-8")
        )
        text = json.dumps(payload)
        text = text.replace("module.shop.checkout", self._target_id)
        payload = json.loads(text)
        pack = request.evidence_pack
        payload["draft"]["scope"] = {
            "repository": pack.repository.repository_id,
            "root": str(self._root.resolve()),
            "branch": pack.repository.branch,
            "commit": pack.repository.commit,
            "dirty": pack.repository.dirty,
            "working_tree_hash": pack.repository.working_tree_hash,
        }
        for field in (
            "contract_version", "run_id", "target_id", "operation",
            "attempt", "snapshot_id", "idempotency_key",
        ):
            payload[field] = getattr(request, field)
        translation = _fake_to_pack_evidence_ids(pack)
        for claim in payload["draft"]["claims"]:
            claim["evidence_ids"] = [
                translation.get(evidence_id, evidence_id)
                for evidence_id in claim["evidence_ids"]
            ]
        return ExtractionResult.model_validate(payload)

    def verify(self, request):
        from knowledge_compiler.contracts.semantic import VerificationResult

        verifications = []
        for claim in request.claims:
            verifications.append(
                {
                    "claim_id": claim.claim_id,
                    "status": "supported",
                    "verifier": "stub-verifier-v1",
                    "evidence_ids": [e.evidence_id for e in claim.evidence],
                    "excerpt_hashes": [e.excerpt_hash for e in claim.evidence],
                    "excerpts": [e.excerpt for e in claim.evidence],
                    "verification_request_digest": request.verification_request_digest,
                }
            )
        return VerificationResult.model_validate(
            {
                "contract_version": request.contract_version,
                "run_id": request.run_id,
                "target_id": request.target_id,
                "operation": "verify",
                "attempt": request.attempt,
                "snapshot_id": request.snapshot_id,
                "idempotency_key": request.idempotency_key,
                "verification_request_digest": request.verification_request_digest,
                "verifications": verifications,
            }
        )


def _fake_to_pack_evidence_ids(pack) -> dict:
    fake_pack = json.loads(
        (FIXTURES / "evidence-pack.json").read_text(encoding="utf-8")
    )
    by_range = {
        (item.path, item.start_line, item.end_line): item.id
        for item in pack.evidence
    }
    translation = {}
    for item in fake_pack["evidence"]:
        match = by_range.get((item["path"], item["start_line"], item["end_line"]))
        if match is not None:
            translation[item["id"]] = match
    return translation


class RecordingPlannerWorker(StubRealWorker):
    def extract(self, request):
        from knowledge_compiler.planning.module import plan_one_module

        survey = getattr(self, "_survey", None)
        if survey is not None:
            self.planner_output = plan_one_module(
                getattr(self, "_plan_request"), survey
            )
        return super().extract(request)


def make_world(tmp_path: Path):
    from knowledge_compiler.providers.codewiki import CodeWikiEvidenceProvider
    from knowledge_compiler.providers.codewiki_cli import FixtureCodewikiRunner

    copied = tmp_path / "repo"
    shutil.copytree(PROBE, copied)
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main", str(copied)], check=True)
    subprocess.run(["git", "-C", str(copied), "config", "user.email", "t@e.com"], check=True)
    subprocess.run(["git", "-C", str(copied), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(copied), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(copied), "commit", "-qm", "fixture"], check=True
    )
    snapshot = RepositorySnapshot.model_validate(
        {
            "repository_id": REPOSITORY_ID,
            "snapshot_id": SNAPSHOT_ID,
            "root": copied.resolve(),
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
    )
    provider = CodeWikiEvidenceProvider(
        FixtureCodewikiRunner(NORMALIZED), repository_root=copied.resolve()
    )
    from knowledge_compiler.planning.module import plan_one_module
    from knowledge_compiler.contracts.planning import PlanRequest

    survey = provider.inspect(snapshot)
    plan_request = PlanRequest.model_validate(
        {
            "run_id": "m2-real-run-001",
            "repository_id": REPOSITORY_ID,
            "snapshot_id": SNAPSHOT_ID,
            "attempt": 1,
            "idempotency_key": f"m2-real-run-001:plan:1:{SNAPSHOT_ID}",
        }
    )
    plan = plan_one_module(plan_request, survey)
    target_id = plan.targets[0].target.id
    worker = StubRealWorker(copied, target_id, "m2-real-run-001")
    return snapshot, provider, worker, plan


def test_real_provider_fixture_path_publishes_one_generation(tmp_path: Path) -> None:
    from knowledge_compiler.real_slice import run_real_module_slice

    snapshot, provider, worker, plan = make_world(tmp_path)
    output_root = tmp_path / "out"

    outcome = run_real_module_slice(
        repository_root=snapshot.root,
        evidence_provider=provider,
        worker=worker,
        output_root=output_root,
        snapshot=snapshot,
    )

    assert not getattr(outcome, "reason", None), outcome
    knowledge = output_root / ".knowledge"
    assert outcome.canonical_path.is_file()
    assert outcome.card_path.is_file()
    assert outcome.wiki_path.is_file()
    manifest = yaml.safe_load(outcome.manifest_path.read_bytes())
    assert manifest == {
        "active_generation": outcome.generation,
        "agent_views_generation": outcome.generation,
        "wiki_generation": outcome.generation,
    }
    canonical = yaml.safe_load(outcome.canonical_path.read_bytes())
    assert canonical["id"] == outcome.object_id
    assert canonical["validity"]["status"] == "verified"
    assert len(canonical["claims"]) == 4
    assert json.dumps(plan.model_dump(mode="json")).lower().count("claim") == 0


def test_provider_failure_returns_typed_and_publishes_nothing(tmp_path: Path) -> None:
    from knowledge_compiler.real_slice import run_real_module_slice

    snapshot, provider, worker, _ = make_world(tmp_path)

    class ExplodingProvider:
        def ensure_index(self, _snapshot):
            raise ValueError("provider exploded")

    outcome = run_real_module_slice(
        repository_root=snapshot.root,
        evidence_provider=ExplodingProvider(),
        worker=worker,
        output_root=tmp_path / "out",
        snapshot=snapshot,
    )
    assert outcome.reason == "validation"
    assert not (tmp_path / "out/.knowledge/manifest.yaml").exists()


def test_model_failure_preserves_previous_generation(tmp_path: Path) -> None:
    from knowledge_compiler.real_slice import run_real_module_slice
    from knowledge_compiler.workers.litellm_worker import WorkerTransportError

    snapshot, provider, worker, _ = make_world(tmp_path)
    output_root = tmp_path / "out"
    first = run_real_module_slice(
        repository_root=snapshot.root,
        evidence_provider=provider,
        worker=worker,
        output_root=output_root,
        snapshot=snapshot,
    )
    assert not getattr(first, "reason", None)
    generation_one = {
        path.name: path.read_bytes()
        for path in (output_root / ".knowledge").rglob("*")
        if path.is_file()
    }

    class ModelDown(StubRealWorker):
        def extract(self, request):
            raise WorkerTransportError("model transport failed: down")

    outcome = run_real_module_slice(
        repository_root=snapshot.root,
        evidence_provider=provider,
        worker=ModelDown(snapshot.root, "module.x.y", "m2-real-run-002"),
        output_root=output_root,
        snapshot=snapshot,
        run_id="m2-real-run-002",
    )
    assert outcome.reason == "model"
    current = {
        path.name: path.read_bytes()
        for path in (output_root / ".knowledge").rglob("*")
        if path.is_file()
    }
    assert current == generation_one


def test_publication_failure_preserves_previous_generation(tmp_path: Path) -> None:
    from knowledge_compiler.real_slice import run_real_module_slice

    snapshot, provider, worker, _ = make_world(tmp_path)
    output_root = tmp_path / "out"
    first = run_real_module_slice(
        repository_root=snapshot.root,
        evidence_provider=provider,
        worker=worker,
        output_root=output_root,
        snapshot=snapshot,
    )
    assert not getattr(first, "reason", None)
    generation_one = {
        path.relative_to(output_root).as_posix(): path.read_bytes()
        for path in (output_root / ".knowledge").rglob("*")
        if path.is_file()
    }

    def fail(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError("injected at publish.card.replace")

    outcome = run_real_module_slice(
        repository_root=snapshot.root,
        evidence_provider=provider,
        worker=worker,
        output_root=output_root,
        snapshot=snapshot,
        run_id="m2-real-run-002",
        fault_injector=fail,
    )
    assert outcome.reason == "publication"
    current = {
        path.relative_to(output_root).as_posix(): path.read_bytes()
        for path in (output_root / ".knowledge").rglob("*")
        if path.is_file()
    }
    assert current == generation_one


def test_boundary_stays_clean() -> None:
    result = subprocess_free_boundary_check()
    assert result is True


def subprocess_free_boundary_check() -> bool:
    from knowledge_compiler import real_slice

    source = Path(real_slice.__file__).read_text(encoding="utf-8")
    return "import codewiki" not in source and "from backend" not in source
