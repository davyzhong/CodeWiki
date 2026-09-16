#!/usr/bin/env python3
"""Repo-wide relative-link checker for docs and manifests.

Markdown links are resolved relative to the file that contains them
(same rule as GitHub rendering). Archived material under
docs/materials/archives/ is frozen history and exempt.
Exit code 1 on any broken link; used by CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
IMG = re.compile(r'<img src="([^"]+)"')
EXEMPT = ("docs/materials/archives/",)
EXTERNAL = ("http://", "https://", "mailto:")


def targets_of(text: str) -> set[str]:
    found = set(LINK.findall(text))
    found |= set(IMG.findall(text))
    return found


def main() -> int:
    documents = [ROOT / "README.md", ROOT / "HANDOFF.md"]
    documents += sorted((ROOT / "docs").rglob("*.md"))
    broken: list[str] = []
    checked = 0
    for document in documents:
        relative = document.relative_to(ROOT).as_posix()
        if relative.startswith(EXEMPT):
            continue
        text = document.read_text(encoding="utf-8", errors="ignore")
        for target in sorted(targets_of(text)):
            if target.startswith(EXTERNAL):
                continue
            checked += 1
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                broken.append(f"{relative} -> {target}")
    print(f"link check: {checked} relative links across {len(documents)} files")
    if broken:
        for item in broken:
            print(f"BROKEN: {item}")
        return 1
    print("link check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
