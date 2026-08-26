from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from knowledge_compiler.contracts.human import HumanOverlay


TYPE_DIRECTORIES = {
    "module": "modules",
    "architecture": "architecture",
    "flow": "flows",
    "rule": "rules",
    "tech-stack": "tech-stack",
}
DIRECTORY_TYPES = {value: key for key, value in TYPE_DIRECTORIES.items()}


class OverlayError(ValueError):
    """An active human overlay cannot be trusted by a mutating run."""


def overlay_path(root: Path, object_id: str) -> Path:
    object_type = object_id.split(".", 1)[0]
    try:
        directory = TYPE_DIRECTORIES[object_type]
    except KeyError as error:
        raise OverlayError(f"unknown overlay object type: {object_type}") from error
    return (
        Path(root).resolve()
        / ".knowledge/human"
        / directory
        / f"{object_id}.yaml"
    )


def load_active_overlays(root: Path) -> dict[str, HumanOverlay]:
    """Load active overlays without ever modifying their source bytes."""

    human_root = Path(root).resolve() / ".knowledge/human"
    if not human_root.exists():
        return {}
    if human_root.is_symlink() or not human_root.is_dir():
        raise OverlayError("human overlay root is not a safe directory")
    result: dict[str, HumanOverlay] = {}
    for path in sorted(human_root.rglob("*.yaml")):
        relative = path.relative_to(human_root)
        if relative.parts[:1] == ("archive",):
            continue
        if path.is_symlink() or not path.is_file():
            raise OverlayError(f"overlay is not a regular file: {relative}")
        if len(relative.parts) != 2 or relative.parts[0] not in DIRECTORY_TYPES:
            raise OverlayError(f"overlay path is invalid: {relative}")
        try:
            payload = yaml.safe_load(path.read_bytes())
            overlay = HumanOverlay.model_validate(payload)
        except (OSError, ValueError, yaml.YAMLError, ValidationError) as error:
            raise OverlayError(f"overlay is invalid: {relative}: {error}") from error
        expected = overlay_path(root, overlay.object_id)
        if path.resolve() != expected:
            raise OverlayError(
                f"overlay path disagrees with object identity: {relative}"
            )
        if overlay.object_id in result:
            raise OverlayError(f"duplicate overlay object: {overlay.object_id}")
        result[overlay.object_id] = overlay
    return dict(sorted(result.items()))


__all__ = [
    "DIRECTORY_TYPES",
    "OverlayError",
    "TYPE_DIRECTORIES",
    "load_active_overlays",
    "overlay_path",
]
