from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from knowledge_compiler.config import KnowledgeConfig, load_config


class PreflightFailure(RuntimeError):
    """Raised when an ordered preflight check stops before any model call."""


def _is_git_repository(root: Path | None) -> bool:
    if root is None:
        return False
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-dir"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0


def _has_commit(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0


def run_preflight(
    root: Path | None,
    *,
    config_path: Path | None = None,
    missing_model_profile: bool = False,
    dry_run: bool = False,
    profiles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run ordered checks; every unsupported prerequisite stops before models."""

    if not dry_run:
        if not _is_git_repository(root):
            raise PreflightFailure("not a Git repository")
        if not _has_commit(root):
            raise PreflightFailure("repository has no commit")
        from knowledge_compiler.repository.local_git import (
            LocalGitRepositoryProvider,
            RepositoryResolutionError,
        )

        try:
            provider = LocalGitRepositoryProvider()
            provider.resolve(root)
        except RepositoryResolutionError as error:
            raise PreflightFailure(str(error)) from error
        if config_path is not None:
            try:
                load_config(config_path)
            except ValueError as error:
                raise PreflightFailure(f"invalid config: {error}") from error

    resolved_profiles = profiles or {
        "extraction_profile": "extraction-v1",
        "validation_profile": None,
    }
    if missing_model_profile or not resolved_profiles.get("extraction_profile"):
        raise PreflightFailure("missing model profile configuration")
    return {
        "validation_profile_mode": (
            "separate"
            if resolved_profiles.get("validation_profile")
            else "reuses-extraction-profile"
        ),
    }


__all__ = ["PreflightFailure", "run_preflight"]
