from __future__ import annotations

import sys
from pathlib import Path

import pytest

from knowledge_compiler.storage import GenerationPublisher, PublicationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/storage"))

from test_generation_publication import _verified_inputs  # noqa: E402


def _overlay_source(root: Path) -> Path:
    return root / ".knowledge/human/modules/module.shop.checkout.yaml"


def _overlay_archive(root: Path) -> Path:
    return root / ".knowledge/human/archive/modules/module.shop.checkout.yaml"


def _write_overlay(root: Path) -> bytes:
    path = _overlay_source(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "schema_version: '0.1'\n"
        "object_id: module.shop.checkout\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections:\n"
        "  - field: summary\n"
        "    mode: supplement\n"
        "    text: Human checkout summary.\n"
        "    basis: incident review\n"
        "notes: []\n",
        encoding="utf-8",
    )
    return path.read_bytes()


def _publish_with_overlay(tmp_path: Path, generation: str) -> bytes:
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish_generation(
        generation, ((module, pack),)
    )
    return _write_overlay(tmp_path)


def test_removal_archives_overlay_byte_identically(tmp_path: Path) -> None:
    overlay_bytes = _publish_with_overlay(tmp_path, "generation-001")

    GenerationPublisher(tmp_path).publish_generation(
        "generation-002", (), allow_empty=True
    )

    assert not _overlay_source(tmp_path).exists()
    assert _overlay_archive(tmp_path).read_bytes() == overlay_bytes


@pytest.mark.parametrize(
    "failure_point",
    (
        "publish.overlay-archive.replace",
        "publish.overlay-archive.directory.fsync",
        "publish.overlay-source.delete",
        "publish.manifest.replace",
    ),
)
def test_interrupted_removal_recovers_overlay_to_active(
    tmp_path: Path, failure_point: str
) -> None:
    overlay_bytes = _publish_with_overlay(tmp_path, "generation-001")

    def fail(point: str) -> None:
        if point == failure_point:
            raise OSError(f"injected at {point}")

    with pytest.raises(PublicationError, match=failure_point):
        GenerationPublisher(tmp_path, fault_injector=fail).publish_generation(
            "generation-002", (), allow_empty=True
        )

    GenerationPublisher(tmp_path).recover()
    GenerationPublisher(tmp_path).recover()

    assert _overlay_source(tmp_path).read_bytes() == overlay_bytes
    assert not _overlay_archive(tmp_path).exists()
    assert (
        tmp_path / ".knowledge/objects/modules/module.shop.checkout.yaml"
    ).is_file()
    assert not (
        tmp_path / ".knowledge/state/transactions/generation-002"
    ).exists()


def test_committed_removal_keeps_archive_after_recovery(
    tmp_path: Path,
) -> None:
    overlay_bytes = _publish_with_overlay(tmp_path, "generation-001")

    def fail(point: str) -> None:
        if point == "cleanup.transactions.directory.fsync":
            raise OSError(f"injected at {point}")

    with pytest.raises(PublicationError, match="cleanup"):
        GenerationPublisher(tmp_path, fault_injector=fail).publish_generation(
            "generation-002", (), allow_empty=True
        )

    GenerationPublisher(tmp_path).recover()

    assert not _overlay_source(tmp_path).exists()
    assert _overlay_archive(tmp_path).read_bytes() == overlay_bytes


def test_refuses_to_archive_over_an_existing_archive_file(
    tmp_path: Path,
) -> None:
    overlay_bytes = _publish_with_overlay(tmp_path, "generation-001")
    archive = _overlay_archive(tmp_path)
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"older archived overlay bytes")
    canonical = (
        tmp_path / ".knowledge/objects/modules/module.shop.checkout.yaml"
    )
    canonical_before = canonical.read_bytes()

    with pytest.raises(PublicationError, match="archived overlay"):
        GenerationPublisher(tmp_path).publish_generation(
            "generation-002", (), allow_empty=True
        )

    assert archive.read_bytes() == b"older archived overlay bytes"
    assert _overlay_source(tmp_path).read_bytes() == overlay_bytes
    assert canonical.read_bytes() == canonical_before
