from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


VERSION_PROBE = (
    "from importlib.metadata import version; "
    "print('codewiki ' + version('codewiki'))"
)
SUPPORTED_VERSION_RANGE = ((0, 6), (0, 7))
_TIMEOUT_SECONDS = 120
_MAX_OUTPUT_BYTES = 4 * 1024 * 1024


class CodewikiCliError(RuntimeError):
    """Raised when the public CodeWiki CLI surface fails or is unsupported."""


@dataclass(frozen=True)
class CliResult:
    stdout: str
    returncode: int


_VERSION_PATTERN = re.compile(r"codewiki (\d+)\.(\d+)(?:\.(\d+))?")


def parse_codewiki_version(text: str | None) -> tuple[int, int, int]:
    if not isinstance(text, str):
        raise CodewikiCliError("codewiki version probe returned no text")
    match = _VERSION_PATTERN.search(text)
    if match is None:
        raise CodewikiCliError(f"codewiki version is unparseable: {text[:60]!r}")
    major, minor, patch = match.groups()
    return (int(major), int(minor), int(patch or 0))


def require_supported_version(text: str | None) -> tuple[int, int, int]:
    parsed = parse_codewiki_version(text)
    if not SUPPORTED_VERSION_RANGE[0] <= parsed[:2] < SUPPORTED_VERSION_RANGE[1]:
        raise CodewikiCliError(
            "unsupported codewiki version "
            f"{parsed[0]}.{parsed[1]}.{parsed[2]}; supported range is >=0.6,<0.7"
        )
    return parsed


class CodewikiRunner:
    """Invoke the public CodeWiki CLI with argument arrays only."""

    def version(self) -> str:
        result = subprocess.run(
            [sys.executable, "-c", VERSION_PROBE],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            raise CodewikiCliError("codewiki version probe failed")
        return result.stdout.strip()

    def run(self, argv: list[str], *, root: Path) -> CliResult:
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                check=False,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired as error:
            raise CodewikiCliError(
                "codewiki command timed out: " + " ".join(argv[1:3])
            ) from error
        if len(result.stdout.encode("utf-8", "replace")) > _MAX_OUTPUT_BYTES:
            raise CodewikiCliError("codewiki output exceeded the size bound")
        if result.returncode != 0:
            raise CodewikiCliError(
                "codewiki command failed: " + " ".join(argv[1:3])
            )
        return CliResult(stdout=result.stdout, returncode=result.returncode)


_COMMAND_KEYS = {
    ("repos", "add"): "repos_add",
    ("repos", "scan"): "repos_scan",
    ("graph", "search"): "graph_search",
    ("graph", "explore"): "graph_explore",
    ("graph", "affected"): "graph_affected",
}


class FixtureCodewikiRunner:
    """Deterministic runner over the normalized captured fixtures."""

    def __init__(self, fixture_dir: Path) -> None:
        self._fixture_dir = Path(fixture_dir)
        self._responses: dict[str, object] = {}
        for path in self._fixture_dir.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._responses[payload["command"]] = payload["json_value"]
        self.invoked_commands: list[str] = []

    def version(self) -> str:
        return "codewiki 0.6.5"

    def run(self, argv: list[str], *, root: Path) -> CliResult:
        tokens = argv[1:]
        if tokens[:1] == ["repos"] or tokens[:1] == ["graph"]:
            key = _COMMAND_KEYS.get(tuple(tokens[:2]))
        else:
            key = tokens[0] if tokens else None
        if key is None or key not in self._responses:
            raise CodewikiCliError(
                "command not captured by the fixture surface: " + " ".join(tokens[:2])
            )
        self.invoked_commands.append(key)
        payload = self._responses[key]
        text = json.dumps(payload, ensure_ascii=False) if payload is not None else ""
        return CliResult(stdout=text, returncode=0)


__all__ = [
    "CliResult",
    "CodewikiCliError",
    "CodewikiRunner",
    "FixtureCodewikiRunner",
    "parse_codewiki_version",
    "require_supported_version",
]
