from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.human.overlays import OverlayError, load_active_overlays


def write_overlay(root: Path, relative: str, *, object_id: str) -> Path:
    path = root / ".knowledge/human" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {object_id}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections: []\n"
        "notes: []\n",
        encoding="utf-8",
    )
    return path


def test_loads_valid_active_overlays_and_ignores_archive(tmp_path: Path) -> None:
    write_overlay(
        tmp_path,
        "modules/module.shop.checkout.yaml",
        object_id="module.shop.checkout",
    )
    write_overlay(
        tmp_path,
        "archive/modules/module.shop.retired.yaml",
        object_id="module.shop.retired",
    )

    overlays = load_active_overlays(tmp_path)

    assert tuple(overlays) == ("module.shop.checkout",)


@pytest.mark.parametrize(
    ("relative", "object_id"),
    (
        ("modules/module.shop.inventory.yaml", "module.shop.checkout"),
        ("flows/module.shop.checkout.yaml", "module.shop.checkout"),
    ),
)
def test_rejects_overlay_whose_path_disagrees_with_identity(
    tmp_path: Path, relative: str, object_id: str
) -> None:
    path = write_overlay(tmp_path, relative, object_id=object_id)
    before = path.read_bytes()

    with pytest.raises(OverlayError, match="path"):
        load_active_overlays(tmp_path)

    assert path.read_bytes() == before


def test_rejects_malformed_overlay_without_rewriting_it(tmp_path: Path) -> None:
    path = write_overlay(
        tmp_path,
        "modules/module.shop.checkout.yaml",
        object_id="module.shop.checkout",
    )
    path.write_text("not: [valid", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(OverlayError, match="invalid"):
        load_active_overlays(tmp_path)

    assert path.read_bytes() == before


def test_primary_build_validates_overlays_before_repository_or_provider_work(
    tmp_path: Path, monkeypatch
) -> None:
    from knowledge_compiler.building import run_primary_build
    from knowledge_compiler.human import overlays as overlay_module

    def reject(_root: Path):
        raise OverlayError("invalid overlay fixture")

    monkeypatch.setattr(overlay_module, "load_active_overlays", reject)

    with pytest.raises(OverlayError, match="fixture"):
        run_primary_build(
            repository_root=tmp_path,
            executor="agent",
            evidence_provider=object(),
        )


def test_incremental_update_validates_overlays_before_inventory_or_build(
    tmp_path: Path, monkeypatch
) -> None:
    from knowledge_compiler.cli import _default_config
    from knowledge_compiler.human import overlays as overlay_module
    from knowledge_compiler.incremental.updating import run_incremental_update

    called = False

    def reject(_root: Path):
        raise OverlayError("invalid overlay fixture")

    def build(**_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(overlay_module, "load_active_overlays", reject)

    with pytest.raises(OverlayError, match="fixture"):
        run_incremental_update(
            repository_root=tmp_path,
            executor="agent",
            config=_default_config("zh"),
            build_runner=build,
        )
    assert called is False
