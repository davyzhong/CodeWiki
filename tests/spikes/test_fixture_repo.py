from pathlib import Path
import subprocess

from knowledge_compiler.spikes.fixture_repo import materialize_probe_repo


def test_materialize_probe_repo_creates_committed_snapshot(tmp_path: Path) -> None:
    template = Path("tests/fixtures/probe_repo")
    repo = materialize_probe_repo(template, tmp_path / "probe")

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo.root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    assert repo.commit == head
    assert repo.eligible_files == (
        "pyproject.toml",
        "src/shop/__init__.py",
        "src/shop/api.py",
        "src/shop/checkout.py",
        "src/shop/inventory.py",
    )
