from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.contracts import EvidencePack
from knowledge_compiler.contracts.knowledge import ExtractionResult, ModuleKnowledge
from knowledge_compiler.contracts.semantic import ExtractionRequest, VerificationResult
from knowledge_compiler.storage import GenerationPublisher, PublicationError
from knowledge_compiler.validation.module import (
    apply_verification_result,
    build_verification_request,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fake_provider"
REPOSITORY_ROOT = ROOT / "tests/fixtures/probe_repo"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _verified_inputs() -> tuple[ModuleKnowledge, EvidencePack]:
    extraction_data = deepcopy(_load("module-extraction.json"))
    extraction_data["draft"]["scope"]["root"] = str(REPOSITORY_ROOT)
    extraction = ExtractionResult.model_validate(extraction_data)
    pack_data = deepcopy(_load("evidence-pack.json"))
    pack_data["repository"]["root"] = str(REPOSITORY_ROOT)
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
        request, extraction, REPOSITORY_ROOT
    )
    result = apply_verification_result(
        request,
        extraction,
        verification_request,
        VerificationResult.model_validate(_load("module-verification.json")),
        REPOSITORY_ROOT,
    )
    assert result.is_valid and result.module is not None
    return result.module, pack


def _visible(root: Path) -> dict[str, bytes]:
    knowledge = root / ".knowledge"
    return {
        str(path.relative_to(knowledge)): path.read_bytes()
        for path in sorted(knowledge.rglob("*"))
        if path.is_file() and "state/transactions" not in str(path.relative_to(knowledge))
    }


def test_publishes_all_outputs_and_replaces_manifest_last(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    points: list[str] = []
    publisher = GenerationPublisher(tmp_path, fault_injector=points.append)

    published = publisher.publish("generation-001", module, pack)

    assert published.generation == "generation-001"
    assert published.canonical_path.read_bytes().endswith(b"\n")
    assert published.card_path.read_bytes().startswith(b"# ")
    assert published.wiki_path.read_bytes().startswith(b"# ")
    manifest = yaml.safe_load(published.manifest_path.read_bytes())
    assert manifest == {
        "active_generation": "generation-001",
        "agent_views_generation": "generation-001",
        # The complete Wiki is compiled after publication; the stamp
        # lags until `knowledge compile` succeeds.
        "wiki_generation": None,
    }
    replace_points = [point for point in points if point.endswith(".replace")]
    assert replace_points[-1] == "publish.manifest.replace"
    assert not (tmp_path / ".knowledge/state/transactions/generation-001").exists()


def test_single_publication_rejects_oversized_manifest_before_output_mutation(
    tmp_path: Path,
) -> None:
    module, pack = _verified_inputs()
    before = _visible(tmp_path)

    with pytest.raises(PublicationError, match="size bound"):
        GenerationPublisher(tmp_path).publish(
            "generation-oversized-single",
            module,
            pack,
            pending_targets=("x" * 1_050_000,),
        )

    assert _visible(tmp_path) == before
    assert not (tmp_path / ".knowledge").exists()


def test_batch_publication_rejects_oversized_manifest_before_output_mutation(
    tmp_path: Path,
) -> None:
    module, pack = _verified_inputs()
    before = _visible(tmp_path)

    with pytest.raises(PublicationError, match="size bound"):
        GenerationPublisher(tmp_path).publish_generation(
            "generation-oversized-batch",
            ((module, pack),),
            pending_targets=("x" * 1_050_000,),
        )

    assert _visible(tmp_path) == before
    assert not (tmp_path / ".knowledge").exists()


FAILURE_POINTS = (
    "stage.canonical.write",
    "stage.canonical.flush",
    "stage.canonical.fsync",
    "stage.card.write",
    "stage.card.flush",
    "stage.card.fsync",
    "stage.wiki.write",
    "stage.wiki.flush",
    "stage.wiki.fsync",
    "stage.manifest.write",
    "stage.manifest.flush",
    "stage.manifest.fsync",
    "stage.directory.fsync",
    "backup.canonical.write",
    "backup.canonical.flush",
    "backup.canonical.fsync",
    "backup.card.write",
    "backup.card.flush",
    "backup.card.fsync",
    "backup.wiki.write",
    "backup.wiki.flush",
    "backup.wiki.fsync",
    "backup.manifest.write",
    "backup.manifest.flush",
    "backup.manifest.fsync",
    "backup.directory.fsync",
    "journal.write",
    "journal.flush",
    "journal.fsync",
    "journal.replace",
    "transaction.directory.fsync",
    "publish.canonical.replace",
    "publish.canonical.directory.fsync",
    "publish.card.replace",
    "publish.card.directory.fsync",
    "publish.wiki.replace",
    "publish.wiki.directory.fsync",
    "publish.manifest.replace",
)


@pytest.mark.parametrize("failure_point", FAILURE_POINTS)
def test_failure_and_startup_recovery_preserve_previous_generation(
    tmp_path: Path, failure_point: str
) -> None:
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish("generation-001", module, pack)
    before = _visible(tmp_path)

    def fail(point: str) -> None:
        if point == failure_point:
            raise OSError(f"injected at {point}")

    with pytest.raises(PublicationError, match=failure_point):
        GenerationPublisher(tmp_path, fault_injector=fail).publish(
            "generation-002", module, pack
        )

    GenerationPublisher(tmp_path).recover()

    assert _visible(tmp_path) == before
    assert not (tmp_path / ".knowledge/state/transactions/generation-002").exists()


def test_compiler_failure_happens_before_any_storage_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, pack = _verified_inputs()

    def fail(*_args: object) -> bytes:
        raise ValueError("compiler exploded")

    monkeypatch.setattr("knowledge_compiler.storage.generation.compile_module_card", fail)
    with pytest.raises(PublicationError, match="compiler exploded"):
        GenerationPublisher(tmp_path).publish("generation-001", module, pack)

    assert not (tmp_path / ".knowledge").exists()


def test_copied_model_serialization_failure_happens_before_mutation(
    tmp_path: Path,
) -> None:
    module, pack = _verified_inputs()
    invalid = module.model_copy(update={"summary": object()})

    with pytest.raises(PublicationError, match="compilation failed"):
        GenerationPublisher(tmp_path).publish("generation-001", invalid, pack)

    assert not (tmp_path / ".knowledge").exists()


@pytest.mark.parametrize("generation", ("../escape", "/absolute", ".", "a/b", ""))
def test_rejects_untrusted_generation_before_mutation(
    tmp_path: Path, generation: str
) -> None:
    module, pack = _verified_inputs()
    with pytest.raises(PublicationError, match="generation"):
        GenerationPublisher(tmp_path).publish(generation, module, pack)
    assert not (tmp_path / ".knowledge").exists()


def test_rejects_symlinked_knowledge_root(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".knowledge").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PublicationError, match="symlink"):
        GenerationPublisher(tmp_path).publish("generation-001", module, pack)

    assert list(outside.iterdir()) == []


def test_rejects_output_root_with_symlink_ancestor(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PublicationError, match="symlink"):
        GenerationPublisher(linked / "result").publish(
            "generation-001", module, pack
        )

    assert list(outside.iterdir()) == []


def _with_summary(module: ModuleKnowledge, text: str) -> ModuleKnowledge:
    data = module.model_dump(mode="json")
    data["summary"]["text"] = text
    return ModuleKnowledge.model_validate(data)


@pytest.mark.parametrize(
    "failure_point",
    ("publish.manifest.directory.fsync", "cleanup.transactions.directory.fsync"),
)
def test_post_commit_crash_keeps_new_generation_and_cleans_journal(
    tmp_path: Path, failure_point: str
) -> None:
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish("generation-001", module, pack)
    replacement = _with_summary(module, "Replacement summary for generation two.")

    def fail(point: str) -> None:
        if point == failure_point:
            raise OSError(f"injected at {point}")

    with pytest.raises(PublicationError, match=failure_point):
        GenerationPublisher(tmp_path, fault_injector=fail).publish(
            "generation-002", replacement, pack
        )

    GenerationPublisher(tmp_path).recover()
    GenerationPublisher(tmp_path).recover()

    manifest = yaml.safe_load((tmp_path / ".knowledge/manifest.yaml").read_bytes())
    assert manifest == {
        "active_generation": "generation-002",
        "agent_views_generation": "generation-002",
        "wiki_generation": None,
    }
    canonical = (tmp_path / ".knowledge/objects/modules/module.shop.checkout.yaml").read_text()
    assert "Replacement summary for generation two." in canonical
    assert not (tmp_path / ".knowledge/state/transactions/generation-002").exists()


def test_rejects_unsafe_copied_module_id_before_mutation(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    unsafe = module.model_copy(update={"id": "../../escape"})

    with pytest.raises(PublicationError, match="compilation failed"):
        GenerationPublisher(tmp_path).publish("generation-001", unsafe, pack)

    assert not (tmp_path / ".knowledge").exists()


@pytest.mark.parametrize("value", ("../../escape", "/absolute", "a/b", "", None, 123))
def test_rejects_unsafe_object_id_defense_in_depth(value: object) -> None:
    with pytest.raises(PublicationError, match="object id"):
        GenerationPublisher._validate_object_id(value)


def test_rejects_generation_id_reuse_with_differing_content(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    publisher = GenerationPublisher(tmp_path)
    publisher.publish("generation-001", module, pack)
    before = _visible(tmp_path)
    replacement = _with_summary(module, "Differing summary under a reused id.")

    with pytest.raises(PublicationError, match="generation id reuse"):
        publisher.publish("generation-001", replacement, pack)

    assert _visible(tmp_path) == before


def test_rejects_publish_while_unrecovered_transactions_exist(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    publisher = GenerationPublisher(tmp_path)
    publisher.publish("generation-000", module, pack)
    generation_zero = _visible(tmp_path)
    replacement = _with_summary(module, "First crash leaves a journal behind.")

    def crash_first(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError("injected at publish.card.replace")

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=crash_first).publish(
            "generation-001", replacement, pack
        )
    assert (tmp_path / ".knowledge/state/transactions/generation-001").exists()

    second = _with_summary(module, "Second publication must wait for recovery.")
    with pytest.raises(PublicationError, match="unrecovered transactions"):
        GenerationPublisher(tmp_path).publish("generation-002", second, pack)

    GenerationPublisher(tmp_path).recover()
    assert _visible(tmp_path) == generation_zero
    published = GenerationPublisher(tmp_path).publish("generation-002", second, pack)
    assert "Second publication must wait for recovery." in published.canonical_path.read_text()


def test_recover_rejects_symlinked_transactions_root(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish("generation-001", module, pack)

    precious = tmp_path / "precious"
    (precious / "subdir" / "deeper").mkdir(parents=True)
    (precious / "subdir" / "deeper" / "data.txt").write_text("keep me", encoding="utf-8")
    transactions = tmp_path / ".knowledge/state/transactions"
    transactions.rmdir()
    transactions.symlink_to(precious, target_is_directory=True)

    with pytest.raises(PublicationError, match="symlink"):
        GenerationPublisher(tmp_path).recover()

    assert (precious / "subdir" / "deeper" / "data.txt").exists()


def test_reuse_guard_wraps_unreadable_destination_as_typed_error(
    tmp_path: Path,
) -> None:
    module, pack = _verified_inputs()
    publisher = GenerationPublisher(tmp_path)
    publisher.publish("generation-001", module, pack)
    outside = tmp_path / "outside.txt"
    outside.write_text("decoy", encoding="utf-8")
    wiki = tmp_path / ".knowledge/views/wiki/modules/module.shop.checkout.md"
    wiki.unlink()
    wiki.symlink_to(outside)

    with pytest.raises(PublicationError, match="reuse check failed"):
        publisher.publish("generation-001", module, pack)


def test_recover_reports_symlinked_manifest_as_typed_error(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish("generation-001", module, pack)

    def crash(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError("injected at publish.card.replace")

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=crash).publish(
            "generation-002", module, pack
        )

    manifest = tmp_path / ".knowledge/manifest.yaml"
    decoy = tmp_path / "decoy.yaml"
    decoy.write_text("active_generation: forged", encoding="utf-8")
    manifest.unlink()
    manifest.symlink_to(decoy)

    with pytest.raises(PublicationError, match="unreadable"):
        GenerationPublisher(tmp_path).recover()


def test_recover_skips_stray_entries_but_publish_fails_closed(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    publisher = GenerationPublisher(tmp_path)
    publisher.publish("generation-001", module, pack)
    generation_one = _visible(tmp_path)
    replacement = _with_summary(module, "Crash to leave one journal.")

    def crash(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError("injected at publish.card.replace")

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=crash).publish(
            "generation-002", replacement, pack
        )

    stray = tmp_path / ".knowledge/state/transactions/planted-file"
    stray.write_text("not a transaction", encoding="utf-8")

    GenerationPublisher(tmp_path).recover()

    assert stray.exists()
    assert _visible(tmp_path) == generation_one
    with pytest.raises(PublicationError, match="unrecovered transactions"):
        GenerationPublisher(tmp_path).publish("generation-003", module, pack)


@pytest.mark.parametrize("generation", ("gen.", "trailing.dot."))
def test_rejects_trailing_punctuation_generation_ids(tmp_path: Path, generation: str) -> None:
    module, pack = _verified_inputs()
    with pytest.raises(PublicationError, match="generation"):
        GenerationPublisher(tmp_path).publish(generation, module, pack)
    assert not (tmp_path / ".knowledge").exists()


def test_recovery_is_idempotent_after_interruption(tmp_path: Path) -> None:
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish("generation-001", module, pack)
    before = _visible(tmp_path)

    def fail_publish(point: str) -> None:
        if point == "publish.wiki.directory.fsync":
            raise OSError(point)

    with pytest.raises(PublicationError):
        GenerationPublisher(tmp_path, fault_injector=fail_publish).publish(
            "generation-002", module, pack
        )

    def fail_recovery(point: str) -> None:
        if point == "recovery.card.replace":
            raise OSError(point)

    with pytest.raises(PublicationError, match="recovery.card.replace"):
        GenerationPublisher(tmp_path, fault_injector=fail_recovery).recover()

    GenerationPublisher(tmp_path).recover()
    GenerationPublisher(tmp_path).recover()
    assert _visible(tmp_path) == before
