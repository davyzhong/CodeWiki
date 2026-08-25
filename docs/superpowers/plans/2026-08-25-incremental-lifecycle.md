# Incremental Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explicit updates detect local repository changes before provider sync, atomically remove stale knowledge from safe Agent surfaces, retry pending work, and retire objects only through deterministic proof.

**Architecture:** A tracked eligible-file baseline under `.knowledge/baseline/eligible-files.json` is authoritative for change detection — computed before any CodeWiki sync so provider mutation cannot erase it. A ChangeSet (added/modified/deleted/renamed) drives a reverse Evidence index to derive affected objects; an invalidation transaction marks them stale and atomically removes their Cards before any semantic regeneration. Pending targets persist so retries happen even without new diffs. Retirement requires four deterministic proofs (source absence, exhaustive provider search, inbound-relation refresh, complete queries); model output never authorizes deletion. `knowledge update --executor llm` returns 0 complete / 1 failed / 2 partial-or-stale.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML, Typer, pytest

**Specs:** design §8, §9.7, §12 (incl. 12.1), §13, §15, §16, §18; handoff M5.1-M5.7

---

## Scope and invariants

- Change detection always runs before CodeWiki sync; the baseline never depends on provider cache or Git history depth.
- `.knowledge/` and `.codewiki/` never alter the repository snapshot.
- Affected derivation combines the local ChangeSet with provider hints (hints enrich, never replace).
- Stale objects leave Agent Card views in the same invalidation transaction that marks the canonical object; generation metadata binds for M7 FTS.
- `pending_targets` persist across runs; retries happen even with no new diff.
- Retirement: source absence + exhaustive provider search (exact symbol/path/graph/lexical) + inbound relation refresh + every query completed; inconclusive keeps stale.
- Planner omission never deletes; `insufficient_evidence` never authorizes deletion.
- No human overlays (M6), no complete Wiki/FTS/MCP (M7).

## Planned file structure

```text
src/knowledge_compiler/
├── repository/
│   ├── inventory.py             # persisted eligible-file baseline
│   └── changes.py               # ChangeSet computation
├── incremental/
│   ├── __init__.py
│   ├── invalidation.py          # reverse index + stale marking transaction
│   ├── pending.py               # pending_targets persistence + retry
│   └── retirement.py            # deterministic retirement proofs
└── cli.py                       # + knowledge update
tests/
├── repository/test_changes.py
├── incremental/
│   ├── test_invalidation.py
│   ├── test_pending.py
│   └── test_retirement.py
└── cli/test_update.py
```

### Task 1 (M5.1): This plan

- [ ] Independent plan review; fix until approved; commit.

### Task 2 (M5.2): Tracked baseline and ChangeSet

- [ ] Failing tests: committed modifications, dirty files, new untracked eligible files, deletion, rename (normalized to delete+add unless Git identity and hash prove identity), branch switch, detached/non-descendant switch, shallow clone, cache deletion, exclusions, no-op update.
- [ ] Implement `inventory.py` (persist path/blob/hash/size/language; never content) and `changes.py` (compare before provider sync).
- [ ] Advance `observed_snapshot` and the eligible-file baseline to the current scan after committed safe invalidation even on partial runs.
- [ ] Focused/full tests, reviews, commit `feat: track eligible-file changes`.

### Task 3 (M5.3): Affected derivation and invalidation transaction

- [ ] Failing tests: reverse index from Evidence path/symbol/hash to objects; provider hints enrich but never replace; one-hop relation spread per policy; stale marks carry reason + last verified identity; Cards removed atomically in the same generation; manifest commits matching `active_generation`/`agent_views_generation` in the invalidation transaction; provider failure commits safe invalidation without regeneration; no prior generation + failure = failed return; crash fixtures at each invalidation journal boundary.
- [ ] Implement `invalidation.py`.
- [ ] Focused/full tests, reviews, commit `feat: invalidate affected knowledge atomically`.

### Task 4 (M5.4): Pending targets and selective replanning

- [ ] Failing tests: pending persistence across runs with no diff; full refresh triggers (corrupt baseline, identity change, no source, incompatible provider rebuild); area refresh (entry points, module dirs, routes, topology, communities); ordinary changes schedule only referencing objects; published state separate from target results.
- [ ] Implement `pending.py` + replanning triggers.
- [ ] Focused/full tests, reviews, commit `feat: retry pending knowledge targets`.

### Task 5 (M5.5): Deterministic retirement

- [ ] Failing tests: deletion creates retirement_pending; four-proof requirement; vector/model output forbidden; inbound relation refresh; inconclusive queries keep stale; proven retirement deletes canonical YAML, Card, FTS row contract, plan, and commits manifest generation atomically; verified replacement cancels; `insufficient_evidence` never deletes; crash fixtures at each boundary.
- [ ] Implement `retirement.py`.
- [ ] Focused/full tests, reviews, commit `feat: retire knowledge deterministically`.

### Task 6 (M5.6): `knowledge update`

- [ ] Failing tests: exit 0 complete / 1 failed / 2 partial-stale-pending; report separates snapshot/changeset, invalidation generation, object states, target results, pending targets, provider state, view lag; interruption + idempotent rerun; no-diff pending retry; provider failure partial; later recovery.
- [ ] Implement the `update` command over the orchestrator + invalidation + pending + retirement.
- [ ] Extend the /knowledge-build Skill with the `/knowledge-update` walk: prepare → next → evidence → submit-extraction → verify-next → submit-verification → finalize over the same persisted lease protocol, with protocol tests pinning the file bytes in both archive and package.
- [ ] Focused/full tests, reviews, commit `feat: add knowledge update`.

### Task 7 (M5.7): Exit gate

- [ ] Default Agent Cards never contain stale objects; partial updates preserve stale diagnostics outside safe context; Planner omission never deletes; cache deletion, shallow clone, dirty tree, branch switch, add/modify/delete/rename all recover; target reports and object states distinct; full suite ×2, boundary scan, reviews, milestone review, push approved M5.

## Completion checks

- [ ] Verified-only Agent Cards never contain stale knowledge with matching generation metadata.
- [ ] Partial updates preserve prior diagnostics but exclude them from safe context.
- [ ] Planner/model omission never deletes objects.
- [ ] Cache deletion, shallow clone, dirty tree, and branch switch recover from the tracked baseline.
- [ ] `knowledge update` reports separate canonical states from target results.
