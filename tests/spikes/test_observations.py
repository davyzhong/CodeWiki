import json
from pathlib import Path

from knowledge_compiler.spikes.observations import (
    CommandObservation,
    ProbeBundle,
    sanitize_text,
    write_bundle,
)


def test_sanitize_text_replaces_repo_path_and_api_key() -> None:
    root = Path("/private/tmp/probe")
    value = "path=/private/tmp/probe/src/app.py api_key=sk-secret-value"

    sanitized = sanitize_text(value, root)

    assert sanitized == "path=<REPO>/src/app.py api_key=<REDACTED>"


def test_write_bundle_round_trips_without_absolute_repo_path(tmp_path: Path) -> None:
    root = Path("/private/tmp/probe")
    bundle = ProbeBundle(
        codewiki_version="codewiki 0.6.5",
        repository_commit="abc123",
        commands=[
            CommandObservation(
                name="scan",
                argv=["scan", "<REPO>"],
                returncode=0,
                stdout=sanitize_text(str(root / "src/app.py"), root),
                stderr="",
            )
        ],
    )
    output = tmp_path / "bundle.json"

    write_bundle(bundle, output)
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded["schema_version"] == "0.1"
    assert str(root) not in output.read_text(encoding="utf-8")
