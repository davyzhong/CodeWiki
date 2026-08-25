from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from knowledge_compiler.contracts import EvidenceBudget
from knowledge_compiler.providers.fake import FakeEvidenceProvider


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fake_provider"
REPOSITORY_ROOT = (ROOT / "tests/fixtures/probe_repo").resolve()
GOLDEN = ROOT / "tests/golden"
STABLE_ROOT = "/fixture/probe_repo"

Runner = CliRunner()


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def variant(tmp_path: Path, name: str, mutate=None) -> Path:
    data = deepcopy(load(name))
    if mutate is not None:
        mutate(data)
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def provider(root: Path = REPOSITORY_ROOT) -> FakeEvidenceProvider:
    return FakeEvidenceProvider(fixture_dir=FIXTURES, repository_root=root)


def visible(root: Path) -> dict[str, bytes]:
    knowledge = root / ".knowledge"
    if not knowledge.exists():
        return {}
    return {
        str(path.relative_to(knowledge)): path.read_bytes()
        for path in sorted(knowledge.rglob("*"))
        if path.is_file()
    }


def stable_root(value):
    if isinstance(value, bytes):
        return value.replace(str(REPOSITORY_ROOT).encode(), STABLE_ROOT.encode())
    return {
        name: stable_root(content) for name, content in value.items()
    }


def test_success_publishes_one_generation_matching_golden(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    outcome = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        tmp_path,
    )

    assert not getattr(outcome, "reason", None)
    assert outcome.generation
    assert outcome.object_id == "module.shop.checkout"
    knowledge = tmp_path / ".knowledge"
    assert outcome.canonical_path == knowledge / "objects/modules/module.shop.checkout.yaml"
    assert outcome.card_path == knowledge / "views/cards/module.shop.checkout.md"
    assert outcome.wiki_path == knowledge / "views/wiki/module.shop.checkout.md"
    assert outcome.manifest_path == knowledge / "manifest.yaml"
    assert stable_root(outcome.canonical_path.read_bytes()) == (GOLDEN / "module.yaml").read_bytes()
    assert outcome.card_path.read_bytes() == (GOLDEN / "module-card.md").read_bytes()
    assert outcome.wiki_path.read_bytes() == (GOLDEN / "module-wiki.md").read_bytes()
    assert yaml.safe_load(outcome.manifest_path.read_bytes()) == {
        "active_generation": outcome.generation,
        "agent_views_generation": outcome.generation,
        "wiki_generation": outcome.generation,
    }
    assert set(visible(tmp_path)) == {
        "objects/modules/module.shop.checkout.yaml",
        "views/cards/module.shop.checkout.md",
        "views/wiki/module.shop.checkout.md",
        "manifest.yaml",
    }


def test_repeated_runs_are_byte_identical(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = run_fake_module_slice(
        provider(), FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json", first_root,
    )
    second = run_fake_module_slice(
        provider(), FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json", second_root,
    )

    assert first.generation == second.generation
    assert stable_root(visible(first_root)) == stable_root(visible(second_root))


@pytest.mark.parametrize("name", ("module-extraction.json", "module-verification.json"))
def test_malformed_semantic_json_fails_sanitized(tmp_path: Path, name: str) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    broken = tmp_path / name
    broken.write_text("{not json at all", encoding="utf-8")

    outcome = run_fake_module_slice(
        provider(),
        broken if "extraction" in name else FIXTURES / "module-extraction.json",
        broken if "verification" in name else FIXTURES / "module-verification.json",
        tmp_path / "out",
    )

    assert outcome.reason.endswith("parse")
    assert visible(tmp_path / "out") == {}


def test_malformed_survey_fixture_blocks_provider(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, fixtures)
    (fixtures / "survey.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError):
        FakeEvidenceProvider(fixture_dir=fixtures, repository_root=REPOSITORY_ROOT)


def test_source_hash_mismatch_fails_validation(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    repository = tmp_path / "repo"
    shutil.copytree(REPOSITORY_ROOT, repository)
    (repository / "src/shop/checkout.py").write_text(
        "\n".join(
            [
                "# rewritten checkout module",
                "",
                "class CheckoutService:",
                "    def __init__(self, inventory):",
                "        self.inventory = inventory",
                "",
                "    def checkout(self, sku, quantity):",
                "        raise RuntimeError('rewritten fixture source')",
                "",
                "",
                "# padding line 11",
                "# padding line 12",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    outcome = run_fake_module_slice(
        provider(repository),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        tmp_path / "out",
    )

    assert outcome.reason == "validation"
    assert any("source.content_hash" in item for item in outcome.issues)
    assert visible(tmp_path / "out") == {}


def test_excerpt_hash_mismatch_fails_verification(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    def tamper(data: dict) -> None:
        entry = data["verifications"][1]
        entry["excerpt_hashes"] = [
            "sha256:" + ("0" if not value.endswith("0") else "1") + value[len("sha256:") + 1 :]
            for value in entry["excerpt_hashes"]
        ]

    outcome = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        variant(tmp_path, "module-verification.json", tamper),
        tmp_path / "out",
    )

    assert outcome.reason == "verification"
    assert any("verification.evidence.hashes" in item for item in outcome.issues)
    assert visible(tmp_path / "out") == {}


def test_unknown_evidence_id_fails_validation(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    def tamper(data: dict) -> None:
        data["draft"]["claims"][0]["evidence_ids"] = ["sha256:" + "0" * 64]

    outcome = run_fake_module_slice(
        provider(),
        variant(tmp_path, "module-extraction.json", tamper),
        FIXTURES / "module-verification.json",
        tmp_path / "out",
    )

    assert outcome.reason == "validation"
    assert any("claim.evidence.unknown" in item for item in outcome.issues)
    assert visible(tmp_path / "out") == {}


def test_structural_claim_failure_fails_validation(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    def tamper(data: dict) -> None:
        data["draft"]["responsibilities"] = []

    outcome = run_fake_module_slice(
        provider(),
        variant(tmp_path, "module-extraction.json", tamper),
        FIXTURES / "module-verification.json",
        tmp_path / "out",
    )

    assert outcome.reason == "validation"
    assert any("responsibility.required" in item for item in outcome.issues)
    assert visible(tmp_path / "out") == {}


@pytest.mark.parametrize("status", ("unsupported", "partial", "conflicted"))
def test_non_supported_verification_fails(tmp_path: Path, status: str) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    def tamper(data: dict) -> None:
        data["verifications"][0]["status"] = status

    outcome = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        variant(tmp_path, "module-verification.json", tamper),
        tmp_path / "out",
    )

    assert outcome.reason == "verification"
    assert any("verification.status" in item for item in outcome.issues)
    assert visible(tmp_path / "out") == {}


def test_compiler_rejection_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    def explode(*_args: object) -> bytes:
        raise ValueError("compiler exploded")

    monkeypatch.setattr(
        "knowledge_compiler.storage.generation.compile_module_card", explode
    )

    outcome = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        tmp_path / "out",
    )

    assert outcome.reason == "publication"
    assert visible(tmp_path / "out") == {}


def test_publication_replacement_failure_first_run_publishes_nothing(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    def fail(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError("injected at publish.card.replace")

    outcome = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        tmp_path / "out",
        fault_injector=fail,
    )

    assert outcome.reason == "publication"
    assert visible(tmp_path / "out") == {}


def test_failed_update_preserves_generation_n(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    output_root = tmp_path / "out"
    first = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        output_root,
    )
    assert not getattr(first, "reason", None)
    generation_n = visible(output_root)

    def rewritten(data: dict) -> None:
        data["draft"]["summary"]["text"] = (
            "Rewritten summary that must never become visible."
        )

    def fail(point: str) -> None:
        if point == "publish.card.replace":
            raise OSError("injected at publish.card.replace")

    outcome = run_fake_module_slice(
        provider(),
        variant(tmp_path, "module-extraction.json", rewritten),
        FIXTURES / "module-verification.json",
        output_root,
        fault_injector=fail,
    )

    assert outcome.reason == "publication"
    assert visible(output_root) == generation_n
    assert b"Rewritten summary" not in visible(output_root)[
        "objects/modules/module.shop.checkout.yaml"
    ]


def test_budget_rejection_precedes_semantic_consumption(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    broken = tmp_path / "extraction.json"
    broken.write_text("{broken", encoding="utf-8")

    outcome = run_fake_module_slice(
        provider(),
        broken,
        FIXTURES / "module-verification.json",
        tmp_path / "out",
        budget=EvidenceBudget(max_items=1, max_characters=10, max_tokens=1),
    )

    assert outcome.reason == "provider"
    assert "budget" in outcome.message
    assert visible(tmp_path / "out") == {}


def test_cli_reports_provider_failures_with_exit_one(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import app

    result = Runner.invoke(
        app,
        [
            "--repository-root", str(REPOSITORY_ROOT),
            "--fixtures", "relative/fixtures/path",
            "--extraction", str(FIXTURES / "module-extraction.json"),
            "--verification", str(FIXTURES / "module-verification.json"),
            "--output-root", str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "provider failure" in result.output
    assert "Traceback" not in result.output
    assert not (tmp_path / "out/.knowledge/manifest.yaml").exists()

    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, fixtures)
    (fixtures / "survey.json").write_text("{broken", encoding="utf-8")
    malformed = Runner.invoke(
        app,
        [
            "--repository-root", str(REPOSITORY_ROOT),
            "--fixtures", str(fixtures),
            "--extraction", str(FIXTURES / "module-extraction.json"),
            "--verification", str(FIXTURES / "module-verification.json"),
            "--output-root", str(tmp_path / "out"),
        ],
    )

    assert malformed.exit_code == 1
    assert malformed.exception is None or isinstance(malformed.exception, SystemExit)
    assert "provider failure" in malformed.output
    assert "Traceback" not in malformed.output


def test_deeply_nested_json_fails_sanitized(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    deep = tmp_path / "extraction.json"
    deep.write_text("[" * 20000 + "]" * 20000, encoding="utf-8")

    outcome = run_fake_module_slice(
        provider(), deep, FIXTURES / "module-verification.json", tmp_path / "out"
    )

    assert outcome.reason == "extraction.parse"
    assert visible(tmp_path / "out") == {}


def test_post_commit_cleanup_failure_reports_committed_success(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    def fail(point: str) -> None:
        if point == "cleanup.transactions.directory.fsync":
            raise OSError("injected at cleanup.transactions.directory.fsync")

    outcome = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        tmp_path,
        fault_injector=fail,
    )

    assert not getattr(outcome, "reason", None)
    assert outcome.manifest_path.exists()
    assert yaml.safe_load(outcome.manifest_path.read_bytes()) == {
        "active_generation": outcome.generation,
        "agent_views_generation": outcome.generation,
        "wiki_generation": outcome.generation,
    }
    assert outcome.canonical_path.exists()
    assert not (tmp_path / ".knowledge/state/transactions").exists() or not any(
        (tmp_path / ".knowledge/state/transactions").iterdir()
    )


def test_failure_messages_are_bounded(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    huge = "x" * 1_000_000

    def tamper(data: dict) -> None:
        data["draft"]["summary"]["claim_ids"] = [
            f"module.shop.checkout.claim.{huge}"
        ]

    outcome = run_fake_module_slice(
        provider(),
        variant(tmp_path, "module-extraction.json", tamper),
        FIXTURES / "module-verification.json",
        tmp_path / "out",
    )

    assert outcome.reason == "extraction.contract"
    assert len(outcome.message) < 4000
    assert visible(tmp_path / "out") == {}


@pytest.mark.parametrize(
    "damage",
    ("delete-card", "tamper-wiki", "symlink-manifest"),
)
def test_committed_probe_requires_full_byte_identical_tree(
    tmp_path: Path, damage: str
) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    output_root = tmp_path / "out"
    first = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        output_root,
    )
    assert not getattr(first, "reason", None)
    knowledge = output_root / ".knowledge"

    if damage == "delete-card":
        (knowledge / "views/cards/module.shop.checkout.md").unlink()
    elif damage == "tamper-wiki":
        (knowledge / "views/wiki/module.shop.checkout.md").write_text(
            "TAMPERED CONTENT\n", encoding="utf-8"
        )
    else:
        manifest = knowledge / "manifest.yaml"
        decoy = tmp_path / "decoy.yaml"
        decoy.write_text(
            f"active_generation: {first.generation}\n", encoding="utf-8"
        )
        manifest.unlink()
        manifest.symlink_to(decoy)

    def fail(point: str) -> None:
        if point == "publish.canonical.replace":
            raise OSError("injected at publish.canonical.replace")

    outcome = run_fake_module_slice(
        provider(),
        FIXTURES / "module-extraction.json",
        FIXTURES / "module-verification.json",
        output_root,
        fault_injector=fail,
    )

    assert outcome.reason == "publication"


def test_duplicate_json_key_message_is_bounded(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import run_fake_module_slice

    huge = "k" * 1_000_000
    duplicated = tmp_path / "extraction.json"
    duplicated.write_text('{"%s": 1, "%s": 2}' % (huge, huge), encoding="utf-8")

    outcome = run_fake_module_slice(
        provider(), duplicated, FIXTURES / "module-verification.json", tmp_path / "out"
    )

    assert outcome.reason == "extraction.parse"
    assert len(outcome.message) < 4000


def test_cli_provider_failure_strips_terminal_escapes(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import app

    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, fixtures)
    huge = "k" * 500_000 + "\x1b]52;c;aGVsbG8=\x07"
    (fixtures / "survey.json").write_text(
        '{"%s": 1, "%s": 2}' % (huge, huge), encoding="utf-8"
    )

    result = Runner.invoke(
        app,
        [
            "--repository-root", str(REPOSITORY_ROOT),
            "--fixtures", str(fixtures),
            "--extraction", str(FIXTURES / "module-extraction.json"),
            "--verification", str(FIXTURES / "module-verification.json"),
            "--output-root", str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert len(result.output) < 8000
    assert "\x1b" not in result.output


def test_cli_help_and_missing_options() -> None:
    from knowledge_compiler.vertical_slice import app

    result = Runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output

    missing = Runner.invoke(app, [])
    assert missing.exit_code != 0
    assert missing.exception is None or isinstance(missing.exception, SystemExit)
    assert "Traceback" not in (missing.output + str(missing.exception))


def test_cli_publishes_with_exit_zero(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import app

    output_root = tmp_path / "out"
    result = Runner.invoke(
        app,
        [
            "--repository-root", str(REPOSITORY_ROOT),
            "--fixtures", str(FIXTURES),
            "--extraction", str(FIXTURES / "module-extraction.json"),
            "--verification", str(FIXTURES / "module-verification.json"),
            "--output-root", str(output_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "module.shop.checkout" in result.output
    assert (output_root / ".knowledge/manifest.yaml").exists()


def test_cli_reports_failure_with_exit_one(tmp_path: Path) -> None:
    from knowledge_compiler.vertical_slice import app

    broken = tmp_path / "extraction.json"
    broken.write_text("{broken", encoding="utf-8")

    result = Runner.invoke(
        app,
        [
            "--repository-root", str(REPOSITORY_ROOT),
            "--fixtures", str(FIXTURES),
            "--extraction", str(broken),
            "--verification", str(FIXTURES / "module-verification.json"),
            "--output-root", str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    assert not (tmp_path / "out/.knowledge/manifest.yaml").exists()
