from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class RepositoryResolutionError(ValueError):
    """Raised when a repository snapshot cannot be resolved safely."""


@dataclass(frozen=True)
class EligibleFileRecord:
    path: str
    blob_id: str | None
    content_hash: str
    size: int
    language: str | None
    supported: bool


_EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".knowledge",
        ".codewiki",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
    }
)
_CREDENTIAL_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        "credentials",
        "credentials.json",
        "secrets",
        "secrets.json",
        "id_rsa",
        "id_ed25519",
    }
)
_CREDENTIAL_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".kdbx"})
_BINARY_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".pdf", ".zip",
        ".gz", ".tgz", ".tar", ".7z", ".rar", ".woff", ".woff2", ".ttf",
        ".eot", ".so", ".dylib", ".dll", ".exe", ".class", ".pyc", ".wasm",
        ".sqlite", ".sqlite3", ".db",
    }
)
_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}
_SUPPORTED_LANGUAGES = frozenset(
    {"python", "typescript", "javascript", "go", "rust", "java"}
)
_DEFAULT_MAX_BYTES = 1_000_000


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _git_text(root: Path, *args: str) -> str:
    result = _run_git(root, *args)
    if result.returncode != 0:
        raise RepositoryResolutionError(
            "git command failed: " + " ".join(args[:2])
        )
    return result.stdout


def _git_lines(root: Path, *args: str) -> list[str]:
    return [line for line in _git_text(root, *args).split("\0") if line]


def _normalized_posix(path: str) -> str | None:
    if not path or "\x00" in path or "\\" in path:
        return None
    parsed = PurePosixPath(path)
    if (
        parsed.is_absolute()
        or path.startswith("/")
        or ".." in parsed.parts
        or parsed.as_posix() in {"", "."}
        or parsed.as_posix() != path
    ):
        return None
    return path


def _path_is_excluded(path: str) -> bool:
    parsed = PurePosixPath(path)
    if any(part in _EXCLUDED_PARTS for part in parsed.parts[:-1]):
        return True
    name = parsed.name
    if name in _EXCLUDED_PARTS or name in _CREDENTIAL_NAMES:
        return True
    if parsed.suffix in _CREDENTIAL_SUFFIXES:
        return True
    return False


def _looks_binary(head: bytes) -> bool:
    return b"\x00" in head


def _normalize_remote(url: str) -> str:
    candidate = url.strip()
    for scheme in ("https://", "http://", "ssh://", "git://", "ftp://"):
        if candidate.startswith(scheme):
            candidate = candidate[len(scheme):]
            break
    if "@" in candidate and ":" in candidate.split("@", 1)[1]:
        user, rest = candidate.split("@", 1)
        if not rest.startswith("/"):
            candidate = rest.replace(":", "/", 1)
    candidate = candidate.rstrip("/")
    if candidate.endswith(".git"):
        candidate = candidate[: -len(".git")]
    if "://" in candidate or "@" in candidate:
        return candidate.lower()
    host, sep, tail = candidate.partition("/")
    if sep and "." in host:
        return f"{host.lower()}/{tail}"
    return candidate.lower()


class LocalGitRepositoryProvider:
    """Resolve one local Git repository into a filtered snapshot identity.

    All Git access uses plumbing commands with argument arrays; repository
    file names and content are always data, never shell input. The dirty
    flag and working-tree hash are computed from the filtered eligible
    inventory so generated knowledge under `.knowledge/` never dirties the
    snapshot.
    """

    def __init__(self, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        self._max_bytes = max_bytes

    def resolve(self, path: str | os.PathLike[str]):
        from knowledge_compiler.contracts.repository import (
            RepositorySnapshot,
            build_snapshot_id,
        )

        root = Path(path).resolve()
        git_dir = _run_git(root, "rev-parse", "--git-dir")
        if git_dir.returncode != 0:
            raise RepositoryResolutionError("path is not a Git repository")
        try:
            commit = _git_text(root, "rev-parse", "HEAD").strip()
        except RepositoryResolutionError as error:
            raise RepositoryResolutionError(
                "repository has no commit; an initial commit is required"
            ) from error

        branch_result = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

        remote_result = _run_git(root, "remote", "get-url", "origin")
        if remote_result.returncode == 0 and remote_result.stdout.strip():
            repository_id = _normalize_remote(remote_result.stdout)
        else:
            # Content-derived identity: the initial commit is stable across
            # moves and renames, unlike any path component.
            initial = _git_text(
                root, "rev-list", "--max-parents=0", "HEAD"
            ).strip().split("\n")[-1]
            repository_id = f"local:{initial}"

        records, deleted_eligible = self._inventory(root)
        if not records and not deleted_eligible:
            raise RepositoryResolutionError(
                "repository has no eligible source files"
            )
        if not any(record.supported for record in records):
            raise RepositoryResolutionError(
                "repository has no eligible files in a supported language"
            )
        dirty = bool(deleted_eligible) or self._has_dirty_eligible(root)
        working_tree_hash = None
        if dirty:
            payload = [
                [record.path, record.content_hash]
                for record in sorted(records, key=lambda record: record.path)
            ]
            working_tree_hash = "sha256:" + hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                .encode("utf-8")
            ).hexdigest()

        return RepositorySnapshot(
            repository_id=repository_id,
            snapshot_id=build_snapshot_id(repository_id, commit, dirty, working_tree_hash),
            root=root,
            branch=branch,
            commit=commit,
            dirty=dirty,
            working_tree_hash=working_tree_hash,
            eligible_files=tuple(
                sorted(record.path for record in records)
            ),
        )

    def inventory(self, path: str | os.PathLike[str]) -> tuple[EligibleFileRecord, ...]:
        records, _ = self._inventory(Path(path).resolve())
        return records

    def diff(self, baseline, current):
        raise NotImplementedError("diff arrives with the M5 incremental lifecycle")

    def _inventory(
        self, root: Path
    ) -> tuple[tuple[EligibleFileRecord, ...], frozenset[str]]:
        tracked: dict[str, str | None] = {}
        for line in _git_lines(root, "ls-files", "-s", "-z"):
            meta, _, path = line.partition("\t")
            normalized = _normalized_posix(path)
            if normalized is None or _path_is_excluded(normalized):
                continue
            blob_id = meta.split(" ")[1] if len(meta.split(" ")) >= 2 else None
            tracked[normalized] = blob_id
        for path in _git_lines(
            root, "ls-files", "--others", "--exclude-standard", "-z"
        ):
            normalized = _normalized_posix(path)
            if normalized is None or _path_is_excluded(normalized):
                continue
            tracked.setdefault(normalized, None)

        records: list[EligibleFileRecord] = []
        existing: set[str] = set()
        for path in sorted(tracked):
            candidate = root.joinpath(*PurePosixPath(path).parts)
            if candidate.is_symlink() or not candidate.is_file():
                continue
            existing.add(path)
            data = candidate.read_bytes()
            if (
                len(data) > self._max_bytes
                or _looks_binary(data[:8192])
                or PurePosixPath(path).suffix in _BINARY_SUFFIXES
            ):
                continue
            language = _LANGUAGE_BY_SUFFIX.get(PurePosixPath(path).suffix)
            records.append(
                EligibleFileRecord(
                    path=path,
                    blob_id=tracked[path],
                    content_hash="sha256:"
                    + hashlib.sha256(data).hexdigest(),
                    size=len(data),
                    language=language,
                    supported=language in _SUPPORTED_LANGUAGES,
                )
            )
        deleted = frozenset(set(tracked) - existing)
        return tuple(records), deleted

    def _has_dirty_eligible(self, root: Path) -> bool:
        status = _run_git(
            root,
            "status",
            "--porcelain",
            "-z",
            "--untracked-files=all",
            "--no-renames",
        )
        if status.returncode != 0:
            raise RepositoryResolutionError("git status failed")
        entries = [line for line in status.stdout.split("\0") if line]
        for entry in entries:
            path = entry[3:] if entry[1:2] == " " or entry[:2] in {"??", "!!"} else entry[2:]
            path = path.split(" -> ")[-1].strip('"')
            normalized = _normalized_posix(path)
            if normalized is not None and not _path_is_excluded(normalized):
                return True
        return False


__all__ = [
    "EligibleFileRecord",
    "LocalGitRepositoryProvider",
    "RepositoryResolutionError",
]
