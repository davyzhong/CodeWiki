from pathlib import Path
import sys

from knowledge_compiler.spikes.cli_probe import run_cli_probe
from knowledge_compiler.spikes.fixture_repo import materialize_probe_repo


def test_run_cli_probe_records_every_documented_command(tmp_path: Path) -> None:
    repo = materialize_probe_repo(Path("tests/fixtures/probe_repo"), tmp_path / "repo")
    observations = run_cli_probe("tests/support/fake_codewiki.py", repo)

    names = {item.name for item in observations}
    assert {
        "version",
        "repos_add",
        "analyze",
        "repos_scan",
        "graph_search",
        "graph_explore",
        "graph_affected",
        "update",
        "graph_search_after_update",
    } <= names
    assert all(item.json_value is not None or item.name == "version" for item in observations)
    assert all("/" not in item.argv[0] for item in observations)
    assert not (repo.root / "storage").exists()
    assert not (repo.root.parent / "storage").exists()


def test_run_cli_probe_records_nonzero_responses(tmp_path: Path) -> None:
    repo = materialize_probe_repo(Path("tests/fixtures/probe_repo"), tmp_path / "repo")

    observations = run_cli_probe("/usr/bin/false", repo)

    assert observations
    assert all(item.returncode != 0 for item in observations)


def test_run_cli_probe_falls_back_to_public_package_metadata_for_version(tmp_path: Path) -> None:
    repo = materialize_probe_repo(Path("tests/fixtures/probe_repo"), tmp_path / "repo")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "codewiki"
    executable.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    executable.chmod(0o755)
    python = bin_dir / "python"
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    python.chmod(0o755)

    observations = run_cli_probe(str(executable), repo)

    package_version = next(item for item in observations if item.name == "package_version")
    assert package_version.returncode == 0
    assert package_version.stdout.strip().startswith("codewiki ")
