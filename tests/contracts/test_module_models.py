from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_compiler.contracts.knowledge import (
    Claim,
    ClaimBackedText,
    ClaimVerification,
    Confidence,
    Dependency,
    DraftClaim,
    DraftModuleKnowledge,
    ExtractionResult,
    ModuleKnowledge,
    Provenance,
    PublicInterface,
    Relation,
    Responsibility,
    Scope,
    Validity,
)


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
GENERATED_AT = datetime(2026, 8, 25, 9, 30, tzinfo=timezone.utc)


def scope_data() -> dict[str, object]:
    return {
        "repository": "repo.shop",
        "root": Path("/work/shop"),
        "branch": "main",
        "commit": "abc123",
        "dirty": False,
        "working_tree_hash": None,
    }


def confidence_data(score: float = 0.9) -> dict[str, object]:
    return {"score": score, "basis": "direct source evidence"}


def draft_claim_data(
    claim_id: str,
    statement: str,
    evidence_ids: tuple[str, ...],
) -> dict[str, object]:
    return {
        "id": claim_id,
        "statement": statement,
        "evidence_ids": evidence_ids,
        "confidence": confidence_data(),
        "required": True,
    }


def draft_data() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "id": "module.checkout.payment",
        "type": "module",
        "title": "Payment module",
        "scope": scope_data(),
        "summary": {
            "text": "Charges an order through a payment gateway.",
            "claim_ids": ("claim.summary",),
        },
        "responsibilities": (
            {
                "text": "Creates payment charges.",
                "claim_ids": ("claim.charge",),
            },
        ),
        "public_interfaces": (
            {
                "name": "charge",
                "description": "Charges an order.",
                "claim_ids": ("claim.charge",),
            },
        ),
        "dependencies": (
            {
                "target": "module.vendor.gateway",
                "description": "Sends charge requests.",
                "claim_ids": ("claim.dependency",),
            },
        ),
        "relations": (
            {
                "predicate": "depends_on",
                "target": "module.vendor.gateway",
                "claim_ids": ("claim.dependency",),
            },
        ),
        "claims": (
            draft_claim_data("claim.summary", "The module charges orders.", (HASH_B,)),
            draft_claim_data("claim.charge", "charge is public.", (HASH_A,)),
            draft_claim_data(
                "claim.dependency", "The gateway is a dependency.", (HASH_C,)
            ),
        ),
        "confidence": confidence_data(0.85),
    }


def provenance_data() -> dict[str, object]:
    return {
        "execution_mode": "fake",
        "model": "fixture-model-v1",
        "prompt_version": "module-extraction-v1",
        "schema_version": "0.1",
        "generated_at": GENERATED_AT,
    }


def verification_data(evidence_id: str) -> dict[str, object]:
    return {
        "status": "supported",
        "verifier": "fixture-verifier-v1",
        "evidence_ids": (evidence_id,),
        "excerpt_hashes": (HASH_C,),
        "verification_request_digest": HASH_B,
    }


def canonical_data() -> dict[str, object]:
    draft = draft_data()
    claims = []
    for item in draft["claims"]:
        claim = dict(item)
        claim["verification"] = verification_data(claim["evidence_ids"][0])
        claims.append(claim)
    return {
        **draft,
        "claims": tuple(claims),
        "provenance": provenance_data(),
        "validity": {
            "status": "verified",
            "verified_commit": "abc123",
            "stale_reason": None,
            "validation_report": ("structural", "semantic"),
        },
    }


def test_valid_draft_and_explicit_versioned_extraction_result() -> None:
    draft = DraftModuleKnowledge.model_validate(draft_data())
    result = ExtractionResult.model_validate(
        {
            "contract_version": "0.1",
            "draft": draft,
            "provenance": provenance_data(),
        }
    )

    assert isinstance(draft.claims[0], DraftClaim)
    assert draft.claims[0].confidence == Confidence.model_validate(confidence_data())
    assert "validity" not in DraftModuleKnowledge.model_fields
    assert result.provenance.generated_at == GENERATED_AT
    assert result.provenance.prompt_version == "module-extraction-v1"


def test_valid_canonical_module_requires_supported_claims() -> None:
    module = ModuleKnowledge.model_validate(canonical_data())

    assert type(module) is ModuleKnowledge
    assert type(module.claims[0]) is Claim
    assert module.claims[0].verification.status == "supported"
    assert module.validity.status == "verified"
    assert module.provenance == Provenance.model_validate(provenance_data())
    assert module.confidence == Confidence.model_validate(confidence_data(0.85))
    assert DraftModuleKnowledge is not ModuleKnowledge


@pytest.mark.parametrize(
    "bad_id",
    (
        "module.payment",
        "Module.checkout.payment",
        "module.checkout.payment details",
        "module..payment",
        " module.checkout.payment",
    ),
)
def test_rejects_invalid_stable_module_id(bad_id: str) -> None:
    data = draft_data()
    data["id"] = bad_id

    with pytest.raises(ValidationError, match="module"):
        DraftModuleKnowledge.model_validate(data)


def test_rejects_duplicate_claim_ids() -> None:
    data = draft_data()
    data["claims"] = (*data["claims"], data["claims"][0])

    with pytest.raises(ValidationError, match="duplicate Claim IDs"):
        DraftModuleKnowledge.model_validate(data)


@pytest.mark.parametrize(
    ("field", "duplicate"),
    (
        (
            "public_interfaces",
            {
                "name": "charge",
                "description": "Duplicate interface.",
                "claim_ids": ("claim.charge",),
            },
        ),
        (
            "dependencies",
            {
                "target": "module.vendor.gateway",
                "description": "Duplicate dependency.",
                "claim_ids": ("claim.dependency",),
            },
        ),
    ),
)
def test_rejects_duplicate_named_payload_entries(
    field: str, duplicate: dict[str, object]
) -> None:
    data = draft_data()
    data[field] = (*data[field], duplicate)

    with pytest.raises(ValidationError, match="duplicate"):
        DraftModuleKnowledge.model_validate(data)


@pytest.mark.parametrize(
    "field",
    ("summary", "responsibilities", "public_interfaces", "dependencies", "relations"),
)
def test_every_factual_payload_requires_a_claim(field: str) -> None:
    data = draft_data()
    if field == "summary":
        data[field] = {**data[field], "claim_ids": ()}
    else:
        data[field] = ({**data[field][0], "claim_ids": ()},)

    with pytest.raises(ValidationError, match="claim_ids"):
        DraftModuleKnowledge.model_validate(data)


@pytest.mark.parametrize("field", ("summary", "relations"))
def test_rejects_unknown_claim_references(field: str) -> None:
    data = draft_data()
    if field == "summary":
        data[field] = {**data[field], "claim_ids": ("claim.unknown",)}
    else:
        data[field] = ({**data[field][0], "claim_ids": ("claim.unknown",)},)

    with pytest.raises(ValidationError, match="unknown Claim"):
        DraftModuleKnowledge.model_validate(data)


def test_rejects_unsupported_canonical_claim_verification() -> None:
    data = canonical_data()
    claims = list(data["claims"])
    claims[0] = {
        **claims[0],
        "verification": {**claims[0]["verification"], "status": "unsupported"},
    }
    data["claims"] = claims

    with pytest.raises(ValidationError, match="supported"):
        ModuleKnowledge.model_validate(data)


def test_canonical_claim_itself_rejects_unsupported_verification() -> None:
    claim = draft_claim_data("claim.summary", "The module charges orders.", (HASH_B,))
    claim["verification"] = {
        **verification_data(HASH_B),
        "status": "unsupported",
    }

    with pytest.raises(ValidationError, match="supported"):
        Claim.model_validate(claim)


def test_verified_validity_requires_every_required_claim_to_be_supported() -> None:
    data = canonical_data()
    claims = list(data["claims"])
    claims[0] = {
        **claims[0],
        "verification": {**claims[0]["verification"], "status": "partial"},
    }
    data["claims"] = claims

    with pytest.raises(ValidationError, match="supported"):
        ModuleKnowledge.model_validate(data)


def test_scope_is_complete_and_requires_an_absolute_root() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        Scope.model_validate({**scope_data(), "root": Path("relative/repo")})

    for field in scope_data():
        incomplete = scope_data()
        incomplete.pop(field)
        with pytest.raises(ValidationError):
            Scope.model_validate(incomplete)


def test_verified_validity_has_safe_optional_state_defaults() -> None:
    validity = Validity.model_validate(
        {"status": "verified", "verified_commit": "abc123"}
    )

    assert validity.stale_reason is None
    assert validity.validation_report == ()


def test_models_are_immutable_and_revalidate_nested_instances() -> None:
    module = DraftModuleKnowledge.model_validate(draft_data())
    with pytest.raises(ValidationError, match="frozen"):
        module.title = "Changed"

    invalid_summary = ClaimBackedText.model_construct(text="fact", claim_ids=())
    data = draft_data()
    data["summary"] = invalid_summary
    with pytest.raises(ValidationError, match="claim_ids"):
        DraftModuleKnowledge.model_validate(data)


def test_equivalent_permutations_have_identical_normalized_dumps() -> None:
    first = canonical_data()
    second = canonical_data()
    second["claims"] = tuple(reversed(second["claims"]))
    second["public_interfaces"] = (
        {
            "name": "refund",
            "description": "Refunds an order.",
            "claim_ids": ("claim.charge",),
        },
        *second["public_interfaces"],
    )
    first["public_interfaces"] = (
        *first["public_interfaces"],
        {
            "name": "refund",
            "description": "Refunds an order.",
            "claim_ids": ("claim.charge",),
        },
    )
    extra_dependency = {
        "target": "module.vendor.audit",
        "description": "Records charge attempts.",
        "claim_ids": ("claim.dependency",),
    }
    first["dependencies"] = (*first["dependencies"], extra_dependency)
    second["dependencies"] = (extra_dependency, *second["dependencies"])
    extra_relation = {
        "predicate": "emits_to",
        "target": "module.vendor.audit",
        "claim_ids": ("claim.dependency",),
    }
    first["relations"] = (*first["relations"], extra_relation)
    second["relations"] = (extra_relation, *second["relations"])
    for dataset in (first, second):
        claims = list(dataset["claims"])
        for index, claim in enumerate(claims):
            if claim["id"] == "claim.summary":
                claims[index] = {**claim, "evidence_ids": (HASH_C, HASH_A)}
                claims[index]["verification"] = {
                    **claim["verification"],
                    "evidence_ids": (HASH_C, HASH_A),
                    "excerpt_hashes": (HASH_A, HASH_B),
                }
        dataset["claims"] = tuple(claims)
    second_claims = list(second["claims"])
    for index, claim in enumerate(second_claims):
        if claim["id"] == "claim.summary":
            second_claims[index] = {
                **claim,
                "evidence_ids": tuple(reversed(claim["evidence_ids"])),
                "verification": {
                    **claim["verification"],
                    "evidence_ids": tuple(
                        reversed(claim["verification"]["evidence_ids"])
                    ),
                    "excerpt_hashes": tuple(
                        reversed(claim["verification"]["excerpt_hashes"])
                    ),
                },
            }
    second["claims"] = tuple(second_claims)

    left = ModuleKnowledge.model_validate(first)
    right = ModuleKnowledge.model_validate(second)

    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert [claim.id for claim in left.claims] == sorted(claim.id for claim in left.claims)
    assert list(left.claims[0].evidence_ids) == sorted(left.claims[0].evidence_ids)
    assert [item.name for item in left.public_interfaces] == ["charge", "refund"]
    assert [item.target for item in left.dependencies] == [
        "module.vendor.audit",
        "module.vendor.gateway",
    ]
    assert [(item.predicate, item.target) for item in left.relations] == [
        ("depends_on", "module.vendor.gateway"),
        ("emits_to", "module.vendor.audit"),
    ]


def test_shared_payload_models_are_concrete_public_contracts() -> None:
    assert Responsibility.model_validate(
        {"text": "Owns charges", "claim_ids": ("claim.charge",)}
    )
    assert PublicInterface.model_validate(
        {"name": "charge", "description": "Charges", "claim_ids": ("claim.charge",)}
    )
    assert Dependency.model_validate(
        {
            "target": "module.vendor.gateway",
            "description": "Calls gateway",
            "claim_ids": ("claim.dependency",),
        }
    )
    assert Relation.model_validate(
        {
            "predicate": "depends_on",
            "target": "module.vendor.gateway",
            "claim_ids": ("claim.dependency",),
        }
    )
    assert ClaimVerification.model_validate(verification_data(HASH_A))
    assert Validity.model_validate(canonical_data()["validity"])


def test_task_two_contracts_are_available_from_the_contracts_package() -> None:
    from knowledge_compiler import contracts

    assert contracts.DraftModuleKnowledge is DraftModuleKnowledge
    assert contracts.ModuleKnowledge is ModuleKnowledge
    assert contracts.ExtractionResult is ExtractionResult
