from __future__ import annotations

import hashlib
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
from knowledge_compiler.contracts.evidence import build_evidence_id
from knowledge_compiler.contracts.knowledge import ExtractionResult, ModuleKnowledge
from knowledge_compiler.contracts.repository import build_snapshot_id
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


def _adversarial_inputs() -> tuple[ModuleKnowledge, EvidencePack]:
    module, pack = _verified_inputs()
    module_data = module.model_dump(mode="json")
    pack_data = pack.model_dump(mode="json")

    commit = "commit`break|cell\n## Forged commit <script>alert(1)</script>"
    branch = "main|forged\n## Forged branch <img src=x onerror=alert(1)>"
    snapshot_id = build_snapshot_id(
        pack.repository.repository_id,
        commit,
        pack.repository.dirty,
        pack.repository.working_tree_hash,
    )
    pack_data["repository"]["commit"] = commit
    pack_data["repository"]["branch"] = branch
    pack_data["repository"]["snapshot_id"] = snapshot_id

    old_to_new_ids: dict[str, str] = {}
    for index, item in enumerate(pack_data["evidence"]):
        old_id = item["id"]
        item["path"] = f"src/unsafe[{index}]|tick`<tag>&.py"
        item["commit"] = commit
        item["excerpt"] = (
            "[evidence](javascript:alert(1))\n<script>evidence()</script>"
        )
        item["excerpt_hash"] = "sha256:" + hashlib.sha256(
            item["excerpt"].encode("utf-8")
        ).hexdigest()
        item["id"] = build_evidence_id(
            pack.repository.repository_id,
            snapshot_id,
            item["path"],
            item["symbol"],
            item["start_line"],
            item["end_line"],
            item["content_hash"],
        )
        old_to_new_ids[old_id] = item["id"]

    evidence_by_id = {item["id"]: item for item in pack_data["evidence"]}
    for claim in module_data["claims"]:
        new_ids = [old_to_new_ids[item] for item in claim["evidence_ids"]]
        claim["evidence_ids"] = new_ids
        claim["verification"]["evidence_ids"] = new_ids
        claim["verification"]["excerpt_hashes"] = [
            evidence_by_id[item]["excerpt_hash"] for item in new_ids
        ]
        claim["statement"] = (
            "Claim [link](javascript:alert(1)) `break` | cell\n"
            "## Forged claim <script>claim()</script> & text"
        )

    module_data["title"] = "Title\n## Forged title <script>title()</script>"
    module_data["scope"]["commit"] = commit
    module_data["scope"]["branch"] = branch
    module_data["validity"]["verified_commit"] = commit
    module_data["summary"]["text"] = (
        "Summary\n## Forged summary <img src=x> [click](javascript:bad)"
    )
    module_data["responsibilities"][0]["text"] = (
        "Responsibility\n- forged list <script>r()</script>"
    )
    module_data["public_interfaces"][0]["name"] = "api`break|cell<tag>"
    module_data["public_interfaces"][0]["description"] = (
        "Interface [link](javascript:bad)\n## Forged interface <b>x</b>"
    )
    module_data["dependencies"][0]["target"] = "dep`break|cell<tag>"
    module_data["dependencies"][0]["description"] = (
        "Dependency\n## Forged dependency <script>d()</script>"
    )
    module_data["relations"][0]["predicate"] = "rel\n## Forged relation"
    module_data["relations"][0]["target"] = "target|cell`break<script>x</script>"

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
    assert r"depends\_on → module.shop.inventory" in text
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


@pytest.mark.parametrize(
    "compiler", (compile_module_yaml, compile_module_card, compile_module_wiki)
)
@pytest.mark.parametrize("hostile_boundary", ("module", "pack"))
def test_compiler_converts_hostile_copy_serialization_failures(
    compiler, hostile_boundary: str
) -> None:
    module, pack = _verified_inputs()
    if hostile_boundary == "module":
        module = module.model_copy(update={"summary": object()})
    else:
        pack = pack.model_copy(update={"evidence": (object(), *pack.evidence[1:])})

    with pytest.raises(CompilerInputError) as caught:
        compiler(module, pack)

    expected = (
        "module contract dump/revalidation failed"
        if hostile_boundary == "module"
        else "evidence pack contract dump/revalidation failed"
    )
    assert str(caught.value) == expected


@pytest.mark.parametrize("compiler", (compile_module_card, compile_module_wiki))
def test_markdown_escapes_adversarial_contract_text_without_structure_injection(
    compiler,
) -> None:
    module, pack = _adversarial_inputs()

    first = compiler(module, pack)
    second = compiler(module, pack)
    text = first.decode("utf-8")

    assert first == second
    assert "\n## Forged" not in text
    assert "\n- forged list" not in text
    assert "<script" not in text
    assert "<img" not in text
    assert "<b>" not in text
    assert "](javascript:" not in text
    assert "&lt;script&gt;" in text
    assert "&amp;" in text
    assert " ⏎ " in text
    assert r"\|" in text
    assert "``api`break" in text
    assert "``dep`break" in text
    assert "[evidence](javascript:" not in text
