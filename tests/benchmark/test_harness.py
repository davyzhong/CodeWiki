from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark"))

from tasks import ManifestError, load_manifest  # noqa: E402


def _manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_manifest_loads_fixture_demo() -> None:
    manifest = load_manifest(ROOT / "benchmark/tasks.d/fixture-demo.yaml")
    assert [task.task_id for task in manifest.tasks] == [
        "probe-greet",
        "probe-report",
    ]
    assert len(manifest.repositories) == 1


def test_manifest_rejects_short_prompts_and_bad_difficulty(tmp_path: Path) -> None:
    path = _manifest(
        tmp_path,
        "schema_version: '0.1'\ntasks:\n"
        "  - task_id: t1\n    repo: local\n    repo_path: r\n"
        "    difficulty: hard\n    prompt: do the thing now please\n"
        "    test_cmd: [pytest]\n    fail_to_pass: [a]\n",
    )
    with pytest.raises(ManifestError, match="difficulty"):
        load_manifest(path)


def test_manifest_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = _manifest(
        tmp_path,
        "schema_version: '0.1'\ntasks:\n"
        "  - task_id: t1\n    repo: local\n    repo_path: r\n"
        "    difficulty: simple\n    prompt: a substantive task description\n"
        "    test_cmd: [pytest]\n    fail_to_pass: [a]\n"
        "  - task_id: t1\n    repo: local\n    repo_path: r\n"
        "    difficulty: simple\n    prompt: another substantive description\n"
        "    test_cmd: [pytest]\n    fail_to_pass: [b]\n",
    )
    with pytest.raises(ManifestError, match="duplicate"):
        load_manifest(path)


def test_manifest_requires_local_repo_path(tmp_path: Path) -> None:
    path = _manifest(
        tmp_path,
        "schema_version: '0.1'\ntasks:\n"
        "  - task_id: t1\n    repo: local\n    difficulty: simple\n"
        "    prompt: a substantive task description here\n"
        "    test_cmd: [pytest]\n    fail_to_pass: [a]\n",
    )
    with pytest.raises(ManifestError, match="repo_path"):
        load_manifest(path)


def test_mcnemar_exact_known_values() -> None:
    from stats import mcnemar_exact

    assert mcnemar_exact(0, 0) == 1.0
    # all discordance one way: p = 2 * (1/2^n)
    assert mcnemar_exact(3, 0) == pytest.approx(0.25)
    assert mcnemar_exact(5, 0) == pytest.approx(2.0 / 32.0)
    # symmetric split cannot reject
    assert mcnemar_exact(2, 2) == pytest.approx(1.0)


def test_wilcoxon_detects_consistent_reduction() -> None:
    from stats import wilcoxon_signed_rank

    # Control consistently spends more: positive deltas across tasks.
    deltas = [10.0] * 12
    _statistic, p = wilcoxon_signed_rank(deltas)
    assert p < 0.01
    _statistic, p_noise = wilcoxon_signed_rank(
        [10.0, -10.0] * 6
    )
    assert p_noise > 0.5


def test_dryrun_runner_end_to_end(tmp_path: Path, capsys) -> None:
    from runner import main

    results = tmp_path / "results"
    code = main(
        [
            "run",
            "--manifest",
            str(ROOT / "benchmark/tasks.d/fixture-demo.yaml"),
            "--backend",
            "dryrun",
            "--seeds",
            "1,2",
            "--results",
            str(results),
        ]
    )
    assert code == 0
    run_dirs = sorted(results.iterdir())
    assert len(run_dirs) == 1
    lines = (run_dirs[0] / "runs.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2 * 2 * 2  # tasks x arms x seeds
    assert (run_dirs[0] / "summary.md").is_file()
    output = capsys.readouterr().out
    assert "H1" in output
