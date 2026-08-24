from pathlib import Path

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


def test_run_cli_probe_records_nonzero_responses(tmp_path: Path) -> None:
    repo = materialize_probe_repo(Path("tests/fixtures/probe_repo"), tmp_path / "repo")

    observations = run_cli_probe("/usr/bin/false", repo)

    assert observations
    assert all(item.returncode != 0 for item in observations)
