from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.incremental.pending import PendingStore, PersistedTarget


def test_pending_store_round_trips(tmp_path: Path) -> None:
    store = PendingStore(tmp_path / "pending.json")
    store.add(
        PersistedTarget(target_id="module.shop.checkout", reason="source-modified")
    )
    loaded = PendingStore(tmp_path / "pending.json")
    assert loaded.targets == (
        PersistedTarget(target_id="module.shop.checkout", reason="source-modified"),
    )


def test_pending_survives_no_diff_retry(tmp_path: Path) -> None:
    store = PendingStore(tmp_path / "pending.json")
    store.add(PersistedTarget(target_id="module.a", reason="stale"))
    # A later update with no new file diff must still see the pending target.
    reloaded = PendingStore(tmp_path / "pending.json")
    assert "module.a" in reloaded.target_ids()


def test_pending_resolved_is_removed(tmp_path: Path) -> None:
    store = PendingStore(tmp_path / "pending.json")
    store.add(PersistedTarget(target_id="module.a", reason="stale"))
    store.resolve("module.a")
    assert store.target_ids() == set()


def test_pending_is_idempotent_on_re_add(tmp_path: Path) -> None:
    store = PendingStore(tmp_path / "pending.json")
    store.add(PersistedTarget(target_id="module.a", reason="one"))
    store.add(PersistedTarget(target_id="module.a", reason="two"))
    assert len(store.targets) == 1
    assert store.targets[0].reason == "two"


def test_pending_store_rejects_tampered_json(tmp_path: Path) -> None:
    path = tmp_path / "pending.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        PendingStore(path)
