# M8 A/B Benchmark Harness

> Pre-registered design: `docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md` (frozen v1.0).
> This directory is harness tooling only — it is NOT part of the `knowledge-compiler` wheel and must stay dependency-free (standard library only).

## Layout

```
benchmark/
  tasks.py     task manifest schema + loading/validation
  backends.py  AgentBackend protocol, DryRunBackend, ClaudeCodeBackend (headless)
  scoring.py   machine verdicts (fail_to_pass red -> green) + run records
  stats.py     paired statistics (exact McNemar, Wilcoxon signed-rank) + summary
  runner.py    CLI entry: per task x arm x seed execution loop
  tasks.d/     task manifests (fixture-demo.yaml for dry runs)
  results/     raw JSONL + summary markdown per run date
```

## Dry run (no API key, no agent, no real build)

```bash
.venv/bin/python benchmark/runner.py run \
  --manifest benchmark/tasks.d/fixture-demo.yaml \
  --backend dryrun --seeds 1,2,3 --results benchmark/results
```

Walks the full pipeline — manifest validation, per-task prepare, context
assembly for the treatment arm, the task x arm x seed loop, JSONL records,
paired statistics, and the summary report — with deterministic synthetic
outcomes (a built-in +2-task treatment bias so the statistics see realistic
data). Verdicts are simulated; nothing under test is executed.

## Real run (requires API key + live knowledge build)

```bash
.venv/bin/python benchmark/runner.py run \
  --manifest benchmark/tasks.d/real-example.yaml \
  --backend claude-code --seeds 1,2,3 --results benchmark/results \
  --knowledge build
```

`--knowledge build` runs `knowledge init` + `knowledge build --executor llm` +
`knowledge compile` per repository at the task's base commit before any arm
runs (control arms never read `.knowledge/`; the treatment arm injects
`knowledge context "<task>"` output once at start). The Claude Code backend
invokes `claude -p --output-format json` with a per-run token cap from the
manifest. Real manifests list actual repositories and `fail_to_pass` tests;
verdicts come from the test command, never from the agent's own claim.

## Records

One JSONL line per (task, arm, seed):
`task_id, arm, seed, success, total_tokens, tool_calls, wall_seconds,
final_diff_hash, notes, backend, model`. The summary applies the
pre-registered H1 (McNemar exact / >= +10pp) and H2 (Wilcoxon signed-rank,
token median -20%) criteria from the frozen design — do not edit those
thresholds between runs.
