from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.compiler import (
    CompilerInputError,
    compile_module_card,
    compile_module_wiki,
    compile_module_yaml,
)
from knowledge_compiler.contracts import EvidencePack
from knowledge_compiler.contracts.knowledge import ExtractionResult, ModuleKnowledge
from knowledge_compiler.contracts.semantic import ExtractionRequest, VerificationResult
from knowledge_compiler.validation.module import (
    apply_verification_result,
    build_verification_request,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fake_provider"
REPOSITORY_ROOT = ROOT / "tests/fixtures/probe_repo"
GOLDEN = ROOT / "tests/golden"


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
    verification_result = VerificationResult.model_validate(
        _load("module-verification.json")
    )
    result = apply_verification_result(
        request,
        extraction,
        verification_request,
        verification_result,
        REPOSITORY_ROOT,
    )
    assert result.is_valid
    assert result.module is not None
    # Compilation does not access the repository, so rebind the already-validated
    # fixture pair to a stable absolute root for portable byte golden files.
    module_data = result.module.model_dump(mode="json")
    module_data["scope"]["root"] = "/fixture/probe_repo"
    pack_data = pack.model_dump(mode="json")
    pack_data["repository"]["root"] = "/fixture/probe_repo"
    return (
        ModuleKnowledge.model_validate(module_data),
        EvidencePack.model_validate(pack_data),
    )


def test_compiles_canonical_yaml_bytes() -> None:
    module, pack = _verified_inputs()

    output = compile_module_yaml(module, pack)

    assert isinstance(output, bytes)
    assert output.endswith(b"\n")
    assert output == (GOLDEN / "module.yaml").read_bytes()
    assert yaml.safe_load(output) == module.model_dump(mode="json")


@pytest.mark.parametrize(
    ("compiler", "golden_name"),
    (
        (compile_module_card, "module-card.md"),
        (compile_module_wiki, "module-wiki.md"),
    ),
)
def test_compiles_golden_markdown_with_claim_and_evidence_pointers(
    compiler, golden_name: str
) -> None:
    module, pack = _verified_inputs()

    output = compiler(module, pack)

    assert output == (GOLDEN / golden_name).read_bytes()
    text = output.decode("utf-8")
    assert "module.shop.checkout.claim.inventory-dependency" in text
    assert "src/shop/checkout.py:4-11" in text
    assert "src/shop/inventory.py:1-3" in text
    assert "depends_on → module.shop.inventory" in text
    assert "unsupported explanatory prose" not in text


@pytest.mark.parametrize(
    "compiler", (compile_module_yaml, compile_module_card, compile_module_wiki)
)
def test_output_is_byte_identical_for_permutations_and_repeated_runs(compiler) -> None:
    module, pack = _verified_inputs()
    permuted_module = module.model_copy(
        update={
            "claims": tuple(reversed(module.claims)),
            "public_interfaces": tuple(reversed(module.public_interfaces)),
            "dependencies": tuple(reversed(module.dependencies)),
            "relations": tuple(reversed(module.relations)),
        }
    )
    permuted_pack = pack.model_copy(
        update={
            "evidence": tuple(reversed(pack.evidence)),
            "graph_facts": tuple(reversed(pack.graph_facts)),
        }
    )

    expected = compiler(module, pack)

    assert compiler(module, pack) == expected
    assert compiler(permuted_module, permuted_pack) == expected


@pytest.mark.parametrize(
    "compiler", (compile_module_yaml, compile_module_card, compile_module_wiki)
)
def test_compiler_revalidates_copied_contract_objects(compiler) -> None:
    module, pack = _verified_inputs()
    invalid = module.model_copy(
        update={"summary": module.summary.model_copy(update={"claim_ids": ()})}
    )

    with pytest.raises(CompilerInputError, match="module"):
        compiler(invalid, pack)


@pytest.mark.parametrize(
    "compiler", (compile_module_yaml, compile_module_card, compile_module_wiki)
)
def test_compiler_rejects_repository_and_target_mismatch(compiler) -> None:
    module, pack = _verified_inputs()
    mismatched_target = pack.target.model_copy(update={"id": "module.shop.inventory"})
    mismatched_pack = pack.model_copy(update={"target": mismatched_target})

    with pytest.raises(CompilerInputError, match="target"):
        compiler(module, mismatched_pack)


@pytest.mark.parametrize(
    "compiler", (compile_module_yaml, compile_module_card, compile_module_wiki)
)
def test_compiler_rejects_untrusted_claim_evidence_binding(compiler) -> None:
    module, pack = _verified_inputs()
    first_claim = module.claims[0]
    bad_verification = first_claim.verification.model_copy(
        update={"excerpt_hashes": ("sha256:" + "0" * 64,)}
    )
    bad_claim = first_claim.model_copy(update={"verification": bad_verification})
    changed = module.model_copy(update={"claims": (bad_claim, *module.claims[1:])})

    with pytest.raises(CompilerInputError, match="excerpt hash"):
        compiler(changed, pack)
