from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from knowledge_compiler.contracts.repository import RepositorySnapshot


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )
    return result.stdout


def make_repo(tmp_path: Path, *, remote: bool = True) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("# demo\n", encoding="utf-8")
    package = root / "pyproject.toml"
    package.write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    src = root / "src/demo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "core.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8"
    )
    if remote:
        git(root, "remote", "add", "origin", "https://example.com/demo/repo.git")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial")
    return root


def resolve(root: Path):
    from knowledge_compiler.repository.local_git import LocalGitRepositoryProvider

    return LocalGitRepositoryProvider().resolve(root)


def test_resolves_clean_snapshot_with_filtered_eligible_files(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    snapshot = resolve(root)
    assert isinstance(snapshot, RepositorySnapshot)
    assert snapshot.root == root.resolve()
    assert snapshot.branch == "main"
    assert snapshot.commit == git(root, "rev-parse", "HEAD").strip()
    assert snapshot.dirty is False
    assert snapshot.working_tree_hash is None
    assert "src/demo/core.py" in snapshot.eligible_files
    assert all(not path.startswith(".git/") for path in snapshot.eligible_files)


def test_repository_id_uses_normalized_remote(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    snapshot = resolve(root)
    assert snapshot.repository_id == "example.com/demo/repo"


def test_repository_id_is_move_stable_without_remote(tmp_path: Path) -> None:
    root = make_repo(tmp_path, remote=False)
    snapshot = resolve(root)
    initial = git(root, "rev-list", "--max-parents=0", "HEAD").strip()
    assert snapshot.repository_id == f"local:{initial}"

    moved = tmp_path / "moved-repo"
    shutil.move(str(root), str(moved))
    moved_snapshot = resolve(moved)
    assert moved_snapshot.repository_id == snapshot.repository_id


def test_detached_head_records_null_branch(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    git(root, "checkout", "-q", "--detach", "HEAD")
    snapshot = resolve(root)
    assert snapshot.branch is None
    assert snapshot.dirty is False


def test_dirty_tree_hashes_only_eligible_files(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "src/demo/core.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b + 1\n", encoding="utf-8"
    )
    (root / ".knowledge/state/notes.txt").parent.mkdir(parents=True)
    (root / ".knowledge/state/notes.txt").write_text("junk", encoding="utf-8")
    snapshot = resolve(root)
    assert snapshot.dirty is True
    assert snapshot.working_tree_hash is not None
    assert snapshot.working_tree_hash.startswith("sha256:")

    (tmp_path / "second").mkdir()
    clean = resolve(make_repo(tmp_path / "second"))
    assert clean.dirty is False


def test_ignored_dependency_binary_credential_and_oversize_files_excluded(
    tmp_path: Path,
) -> None:
    root = make_repo(tmp_path)
    (root / ".gitignore").write_text(
        "node_modules/\n*.log\n", encoding="utf-8"
    )
    (root / "node_modules/pkg").mkdir(parents=True)
    (root / "node_modules/pkg/index.js").write_text("x\n", encoding="utf-8")
    (root / "debug.log").write_text("log\n", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    (root / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    (root / "server.key").write_text("PRIVATE\n", encoding="utf-8")
    big = root / "big_source.py"
    big.write_text("# padding\n" * 200_000, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "extras")
    snapshot = resolve(root)
    files = set(snapshot.eligible_files)
    assert "node_modules/pkg/index.js" not in files
    assert "debug.log" not in files
    assert "image.png" not in files
    assert ".env" not in files
    assert "server.key" not in files
    assert "big_source.py" not in files
    assert "src/demo/core.py" in files


def test_knowledge_and_codewiki_directories_excluded_even_when_tracked(
    tmp_path: Path,
) -> None:
    root = make_repo(tmp_path)
    (root / ".knowledge/config.yaml").parent.mkdir()
    (root / ".knowledge/config.yaml").write_text("language: zh\n", encoding="utf-8")
    (root / ".codewiki/cache.bin").parent.mkdir()
    (root / ".codewiki/cache.bin").write_text("x", encoding="utf-8")
    git(root, "add", "-f", ".knowledge/config.yaml", ".codewiki/cache.bin")
    git(root, "commit", "-qm", "managed")
    snapshot = resolve(root)
    assert all(
        not path.startswith((".knowledge/", ".codewiki/"))
        for path in snapshot.eligible_files
    )


def test_symlink_escaping_root_is_excluded(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("print('outside')\n", encoding="utf-8")
    (root / "linked.py").symlink_to(outside)
    snapshot = resolve(root)
    assert "linked.py" not in snapshot.eligible_files


def test_repository_without_commit_stops(tmp_path: Path) -> None:
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
        RepositoryResolutionError,
    )

    root = tmp_path / "empty"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    with pytest.raises(RepositoryResolutionError, match="commit"):
        LocalGitRepositoryProvider().resolve(root)


def test_repository_without_eligible_source_stops(tmp_path: Path) -> None:
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
        RepositoryResolutionError,
    )

    root = make_repo(tmp_path)
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            path.unlink()
    git(root, "add", "-A")
    git(root, "commit", "-qm", "empty")
    with pytest.raises(RepositoryResolutionError, match="eligible"):
        LocalGitRepositoryProvider().resolve(root)


def test_inventory_records_blob_hash_size_and_language(tmp_path: Path) -> None:
    from knowledge_compiler.repository.local_git import (
        EligibleFileRecord,
        LocalGitRepositoryProvider,
    )

    root = make_repo(tmp_path)
    provider = LocalGitRepositoryProvider()
    inventory = provider.inventory(root)
    by_path = {record.path: record for record in inventory}
    core = by_path["src/demo/core.py"]
    assert isinstance(core, EligibleFileRecord)
    assert core.blob_id is not None and len(core.blob_id) == 40
    assert core.content_hash.startswith("sha256:")
    assert core.size > 0
    assert core.language == "python"
    assert core.supported is True
    assert by_path["README.md"].supported is False


def test_unsupported_language_coverage_reported(tmp_path: Path) -> None:
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
        RepositoryResolutionError,
    )

    (tmp_path / "one").mkdir()
    root = make_repo(tmp_path / "one")
    provider = LocalGitRepositoryProvider()
    inventory = provider.inventory(root)
    assert any(record.supported for record in inventory)
    unsupported = [r for r in inventory if not r.supported]
    assert all(r.language in (None, "markdown", "toml", "text") for r in unsupported)

    (tmp_path / "two").mkdir()
    only_docs = make_repo(tmp_path / "two")
    for path in only_docs.rglob("*"):
        if path.suffix == ".py":
            path.unlink()
    git(only_docs, "add", "-A")
    git(only_docs, "commit", "-qm", "docs only")
    with pytest.raises(RepositoryResolutionError, match="supported"):
        LocalGitRepositoryProvider().resolve(only_docs)


def test_shallow_clone_resolves_without_history(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    git(root, "commit", "-q", "--allow-empty", "-m", "second")
    shallow = tmp_path / "shallow"
    subprocess.run(
        [
            "git", "clone", "-q", "--depth", "1",
            "file://" + str(root), str(shallow),
        ],
        check=True,
        capture_output=True,
    )
    snapshot = resolve(shallow)
    assert snapshot.commit == git(shallow, "rev-parse", "HEAD").strip()


def test_monorepo_under_one_git_root(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    other = root / "services/billing"
    other.mkdir(parents=True)
    (other / "main.py").write_text("print('billing')\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "monorepo")
    snapshot = resolve(root)
    assert "services/billing/main.py" in snapshot.eligible_files


def test_diff_is_deferred_until_m5(tmp_path: Path) -> None:
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
    )

    provider = LocalGitRepositoryProvider()
    with pytest.raises(NotImplementedError):
        provider.diff((), ())


def test_resolve_rejects_non_repository(tmp_path: Path) -> None:
    from knowledge_compiler.repository.local_git import (
        LocalGitRepositoryProvider,
        RepositoryResolutionError,
    )

    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(RepositoryResolutionError, match="Git"):
        LocalGitRepositoryProvider().resolve(plain)
