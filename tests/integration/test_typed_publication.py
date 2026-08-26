from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.storage import GenerationPublisher, PublicationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/contracts"))

from test_architecture_models import architecture_payload  # noqa: E402
from test_flow_models import flow_payload  # noqa: E402
from test_rule_models import rule_payload  # noqa: E402
from test_tech_stack_models import tech_stack_payload  # noqa: E402


PAYLOADS = {
    "architecture": architecture_payload,
    "flow": flow_payload,
    "rule": rule_payload,
    "tech-stack": tech_stack_payload,
}
TYPE_DIRECTORIES = {
    "architecture": "objects/architecture",
    "flow": "objects/flows",
    "rule": "objects/rules",
    "tech-stack": "objects/tech-stack",
}


def typed_draft(type_name: str) -> dict:
    payload = dict(PAYLOADS[type_name]())
    payload["claims"] = [
        {k: v for k, v in claim.items() if k != "verification"}
        for claim in payload["claims"]
    ]
    payload["validity"] = None
    return payload


def verification_for(draft: dict, digest: str) -> dict:
    return {
        "contract_version": "0.1",
        "run_id": "typed-run-001",
        "target_id": draft["id"],
        "operation": "verify",
        "attempt": 1,
        "snapshot_id": "typed-snapshot",
        "idempotency_key": f"typed-run-001:{draft['id']}:verify:1:typed-snapshot",
        "verification_request_digest": digest,
        "verifications": [
            {
                "claim_id": claim["id"],
                "status": "supported",
                "verifier": "typed-verifier-v1",
                "evidence_ids": list(claim["evidence_ids"]),
                "excerpt_hashes": ["sha256:" + "2" * 64]
                * len(claim["evidence_ids"]),
                "excerpts": ["excerpt"] * len(claim["evidence_ids"]),
                "verification_request_digest": digest,
            }
            for claim in draft["claims"]
        ],
    }


def canonicalize(type_name: str):
    from knowledge_compiler.validation.typed import apply_typed_verification

    draft = typed_draft(type_name)
    digest = "sha256:" + "4" * 64
    return apply_typed_verification(
        draft_payload=draft,
        verification_result=verification_for(draft, digest),
        verifier="typed-verifier-v1",
    )


@pytest.mark.parametrize("type_name", list(PAYLOADS))
def test_typed_object_publishes_into_its_type_directory(
    tmp_path: Path, type_name: str
) -> None:
    outcome = canonicalize(type_name)
    assert outcome.canonical is not None, outcome.issues
    canonical = outcome.canonical

    published = GenerationPublisher(tmp_path).publish(
        f"gen-{type_name}-001", canonical
    )

    directory = TYPE_DIRECTORIES[type_name]
    assert published.canonical_path == (
        tmp_path / ".knowledge" / directory / f"{canonical.id}.yaml"
    )
    assert published.canonical_path.is_file()
    assert published.card_path.is_file()
    assert published.wiki_path.is_file()
    manifest = yaml.safe_load(published.manifest_path.read_bytes())
    assert manifest == {
        "active_generation": published.generation,
        "agent_views_generation": published.generation,
        "wiki_generation": published.generation,
    }
    reloaded = yaml.safe_load(published.canonical_path.read_bytes())
    assert reloaded["id"] == canonical.id
    assert reloaded["validity"]["status"] == "verified"


@pytest.mark.parametrize("type_name", list(PAYLOADS))
def test_typed_publication_failure_publishes_nothing(
    tmp_path: Path, type_name: str
) -> None:
    outcome = canonicalize(type_name)
    assert outcome.canonical is not None

    def fail(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError("injected at publish.card.replace")

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=fail).publish(
            f"gen-{type_name}-001", outcome.canonical
        )
    GenerationPublisher(tmp_path).recover()

    knowledge = tmp_path / ".knowledge"
    visible = [
        path for path in knowledge.rglob("*") if path.is_file()
    ]
    assert visible == []


def test_five_types_share_the_publication_contract(tmp_path: Path) -> None:
    """All five canonical types traverse one publication machinery."""
    from knowledge_compiler.contracts.knowledge import ModuleKnowledge
    from knowledge_compiler.validation.typed import apply_typed_verification

    from knowledge_compiler.contracts import EvidencePack
    from knowledge_compiler.contracts.knowledge import ExtractionResult
    from knowledge_compiler.contracts.semantic import (
        ExtractionRequest,
        VerificationResult,
    )
    from knowledge_compiler.validation.module import apply_verification_result, build_verification_request

    fixtures = ROOT / "tests/fixtures/fake_provider"
    repository_root = (ROOT / "tests/fixtures/probe_repo").resolve()
    import json as json_module

    extraction_data = json_module.loads(
        (fixtures / "module-extraction.json").read_text(encoding="utf-8")
    )
    extraction_data["draft"]["scope"]["root"] = str(repository_root)
    extraction = ExtractionResult.model_validate(extraction_data)
    pack_data = json_module.loads(
        (fixtures / "evidence-pack.json").read_text(encoding="utf-8")
    )
    pack_data["repository"]["root"] = str(repository_root)
    pack = EvidencePack.model_validate(pack_data)
    request = ExtractionRequest.model_validate(
        {
            "contract_version": extraction.contract_version,
            "run_id": extraction.run_id,
            "target_id": extraction.target_id,
            "operation": extraction.operation,
            "attempt": extraction.attempt,
            "snapshot_id": extraction.snapshot_id,
            "idempotency_key": extraction.idempotency_key,
            "evidence_pack": pack,
        }
    )
    verification_request = build_verification_request(
        request, extraction, repository_root
    )
    verified = apply_verification_result(
        request,
        extraction,
        verification_request,
        VerificationResult.model_validate(
            json_module.loads(
                (fixtures / "module-verification.json").read_text(encoding="utf-8")
            )
        ),
        repository_root,
    )
    assert verified.is_valid and verified.module is not None
    module = verified.module

    tmp = tmp_path / "publish-root"
    tmp.mkdir()
    try:
        published = GenerationPublisher(tmp).publish(
            "gen-all-001", module, pack
        )
        assert published.canonical_path.name == "module.shop.checkout.yaml"
        for type_name in PAYLOADS:
            outcome = apply_typed_verification(
                draft_payload=typed_draft(type_name),
                verification_result=verification_for(
                    typed_draft(type_name), "sha256:" + "4" * 64
                ),
                verifier="typed-verifier-v1",
            )
            assert outcome.canonical is not None
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_two_types_publish_atomically_in_one_generation(
    tmp_path: Path,
) -> None:
    architecture = canonicalize("architecture").canonical
    flow = canonicalize("flow").canonical
    assert architecture is not None
    assert flow is not None

    published = GenerationPublisher(tmp_path).publish_generation(
        "gen-multi-001",
        ((architecture, None), (flow, None)),
    )

    assert tuple(item.object_id for item in published.objects) == (
        architecture.id,
        flow.id,
    )
    assert all(item.canonical_path.is_file() for item in published.objects)
    assert all(item.card_path.is_file() for item in published.objects)
    assert all(item.wiki_path.is_file() for item in published.objects)
    manifest = yaml.safe_load(published.manifest_path.read_bytes())
    assert manifest["active_generation"] == "gen-multi-001"
    assert manifest["agent_views_generation"] == "gen-multi-001"
    assert manifest["wiki_generation"] == "gen-multi-001"
    assert manifest["objects"] == [
        {"id": architecture.id, "type": "architecture"},
        {"id": flow.id, "type": "flow"},
    ]


def test_multi_object_failure_recovers_the_previous_generation(
    tmp_path: Path,
) -> None:
    architecture = canonicalize("architecture").canonical
    flow = canonicalize("flow").canonical
    rule = canonicalize("rule").canonical
    assert architecture is not None
    assert flow is not None
    assert rule is not None
    publisher = GenerationPublisher(tmp_path)
    publisher.publish_generation(
        "gen-multi-001",
        ((architecture, None), (flow, None)),
    )

    knowledge = tmp_path / ".knowledge"

    def visible_bytes() -> dict[str, bytes]:
        return {
            str(path.relative_to(knowledge)): path.read_bytes()
            for path in sorted(knowledge.rglob("*"))
            if path.is_file() and "state/transactions" not in str(path)
        }

    before = visible_bytes()
    card_replacements = 0

    def fail_on_second_card(point: str) -> None:
        nonlocal card_replacements
        if point == "publish.card.replace":
            card_replacements += 1
            if card_replacements == 2:
                raise OSError("injected multi-object publication failure")

    with pytest.raises(PublicationError):
        GenerationPublisher(
            tmp_path, fault_injector=fail_on_second_card
        ).publish_generation(
            "gen-multi-002",
            ((architecture, None), (rule, None)),
        )

    GenerationPublisher(tmp_path).recover()

    assert visible_bytes() == before


def test_next_generation_removes_objects_absent_from_the_new_set(
    tmp_path: Path,
) -> None:
    architecture = canonicalize("architecture").canonical
    flow = canonicalize("flow").canonical
    rule = canonicalize("rule").canonical
    assert architecture is not None
    assert flow is not None
    assert rule is not None
    publisher = GenerationPublisher(tmp_path)
    first = publisher.publish_generation(
        "gen-multi-001",
        ((architecture, None), (flow, None)),
    )
    flow_paths = next(
        item for item in first.objects if item.object_id == flow.id
    )

    publisher.publish_generation(
        "gen-multi-002",
        ((architecture, None), (rule, None)),
    )

    assert not flow_paths.canonical_path.exists()
    assert not flow_paths.card_path.exists()
    assert not flow_paths.wiki_path.exists()


def test_explicit_empty_generation_retires_the_final_object(
    tmp_path: Path,
) -> None:
    architecture = canonicalize("architecture").canonical
    assert architecture is not None
    publisher = GenerationPublisher(tmp_path)
    first = publisher.publish_generation(
        "gen-before-empty", ((architecture, None),)
    )
    paths = first.objects[0]

    published = publisher.publish_generation(
        "gen-empty", (), allow_empty=True
    )

    assert published.objects == ()
    assert not paths.canonical_path.exists()
    assert not paths.card_path.exists()
    assert not paths.wiki_path.exists()
    manifest = yaml.safe_load(published.manifest_path.read_bytes())
    assert manifest["active_generation"] == "gen-empty"
    assert manifest["objects"] == []


def test_interrupted_empty_generation_recovers_the_final_object(
    tmp_path: Path,
) -> None:
    architecture = canonicalize("architecture").canonical
    assert architecture is not None
    publisher = GenerationPublisher(tmp_path)
    published = publisher.publish_generation(
        "gen-before-empty", ((architecture, None),)
    )
    before = {
        "canonical": published.objects[0].canonical_path.read_bytes(),
        "card": published.objects[0].card_path.read_bytes(),
        "wiki": published.objects[0].wiki_path.read_bytes(),
        "manifest": published.manifest_path.read_bytes(),
    }

    def fail(point: str) -> None:
        if point == "publish.card.delete":
            raise OSError("injected empty-generation interruption")

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=fail).publish_generation(
            "gen-empty", (), allow_empty=True
        )

    GenerationPublisher(tmp_path).recover()
    assert published.objects[0].canonical_path.read_bytes() == before["canonical"]
    assert published.objects[0].card_path.read_bytes() == before["card"]
    assert published.objects[0].wiki_path.read_bytes() == before["wiki"]
    assert published.manifest_path.read_bytes() == before["manifest"]


def test_stale_object_commits_with_card_removed_and_wiki_lag_recorded(
    tmp_path: Path,
) -> None:
    architecture = canonicalize("architecture").canonical
    flow = canonicalize("flow").canonical
    assert architecture is not None
    assert flow is not None
    publisher = GenerationPublisher(tmp_path)
    first = publisher.publish_generation(
        "gen-before-invalidation",
        ((architecture, None), (flow, None)),
    )
    architecture_paths = next(
        item for item in first.objects if item.object_id == architecture.id
    )
    wiki_before = architecture_paths.wiki_path.read_bytes()
    stale = architecture.model_copy(
        update={
            "validity": architecture.validity.model_copy(
                update={
                    "status": "stale",
                    "stale_reason": "source-modified: src/core.py",
                }
            )
        }
    )

    publisher.publish_generation(
        "gen-invalidation",
        ((stale, None), (flow, None)),
    )

    assert yaml.safe_load(architecture_paths.canonical_path.read_bytes())[
        "validity"
    ]["status"] == "stale"
    assert not architecture_paths.card_path.exists()
    assert architecture_paths.wiki_path.read_bytes() == wiki_before
    manifest = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["active_generation"] == "gen-invalidation"
    assert manifest["agent_views_generation"] == "gen-invalidation"
    assert manifest["wiki_generation"] == "gen-before-invalidation"


def test_stale_invalidation_failure_recovers_verified_card_and_canonical(
    tmp_path: Path,
) -> None:
    architecture = canonicalize("architecture").canonical
    assert architecture is not None
    publisher = GenerationPublisher(tmp_path)
    publisher.publish_generation(
        "gen-before-invalidation", ((architecture, None),)
    )
    knowledge = tmp_path / ".knowledge"

    def visible_bytes() -> dict[str, bytes]:
        return {
            str(path.relative_to(knowledge)): path.read_bytes()
            for path in sorted(knowledge.rglob("*"))
            if path.is_file() and "state/transactions" not in str(path)
        }

    before = visible_bytes()
    stale = architecture.model_copy(
        update={
            "validity": architecture.validity.model_copy(
                update={
                    "status": "stale",
                    "stale_reason": "source-modified: src/core.py",
                }
            )
        }
    )

    def fail(point: str) -> None:
        if point == "publish.card.delete":
            raise OSError("injected invalidation interruption")

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=fail).publish_generation(
            "gen-invalidation", ((stale, None),)
        )

    GenerationPublisher(tmp_path).recover()
    assert visible_bytes() == before
