from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from knowledge_compiler.repository.changes import Change, ChangeSet, compute_changes
from knowledge_compiler.repository.inventory import (
    FileRecord,
    load_baseline,
    save_baseline,
)


ROOT = Path(__file__).resolve().parents[2]


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=check
    )
    return result.stdout


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@e.com")
    git(root, "config", "user.name", "T")
    (root / "core.py").write_text("x = 1\n", encoding="utf-8")
    (root / "helper.py").write_text("y = 2\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial")
    return root


def baseline_from(root: Path) -> tuple[FileRecord, ...]:
    from knowledge_compiler.repository.local_git import LocalGitRepositoryProvider

    provider = LocalGitRepositoryProvider()
    return tuple(
        FileRecord(
            path=record.path,
            blob_id=record.blob_id,
            content_hash=record.content_hash,
            size=record.size,
            language=record.language,
        )
        for record in provider.inventory(root)
        if record.language == "python"
    )


def test_baseline_round_trips_without_content(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    records = baseline_from(root)
    baseline_path = tmp_path / "eligible-files.json"
    save_baseline(baseline_path, records)
    loaded = load_baseline(baseline_path)
    assert loaded == records
    content = baseline_path.read_text(encoding="utf-8")
    assert "x = 1" not in content  # never stores source content


def test_noop_change_set_is_empty(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    records = baseline_from(root)
    changes = compute_changes(records, baseline_from(root))
    assert changes.added == ()
    assert changes.modified == ()
    assert changes.deleted == ()


def test_modified_file_detected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    baseline = baseline_from(root)
    (root / "core.py").write_text("x = 42\n", encoding="utf-8")
    changes = compute_changes(baseline, baseline_from(root))
    assert changes.modified == ("core.py",)
    assert changes.added == ()
    assert changes.deleted == ()


def test_added_untracked_eligible_detected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    baseline = baseline_from(root)
    (root / "new.py").write_text("z = 3\n", encoding="utf-8")
    changes = compute_changes(baseline, baseline_from(root))
    assert "new.py" in changes.added


def test_deleted_file_detected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    baseline = baseline_from(root)
    (root / "helper.py").unlink()
    changes = compute_changes(baseline, baseline_from(root))
    assert "helper.py" in changes.deleted


def test_rename_becomes_delete_plus_add(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    baseline = baseline_from(root)
    (root / "helper.py").rename(root / "renamed.py")
    changes = compute_changes(baseline, baseline_from(root))
    # Same blob id and content hash prove identity -> recorded as rename.
    assert ("helper.py", "renamed.py") in changes.renamed
    assert "helper.py" not in changes.deleted
    assert "renamed.py" not in changes.added


def test_branch_switch_detected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    baseline = baseline_from(root)
    git(root, "checkout", "-q", "-b", "feature")
    (root / "core.py").write_text("x = 100\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feature change")
    changes = compute_changes(baseline, baseline_from(root))
    assert "core.py" in changes.modified


def test_change_set_is_a_frozen_model() -> None:
    change_set = ChangeSet(added=("a.py",), modified=("b.py",), deleted=(), renamed=())
    assert isinstance(change_set, ChangeSet)
    with pytest.raises(Exception):
        change_set.added = ("c.py",)
