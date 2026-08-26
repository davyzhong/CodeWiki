# Design Conformance Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the audited gaps between the implemented V0.1 technical chain and the approved design without weakening existing fail-closed behavior.

**Architecture:** Keep canonical publication as the only commit boundary. Expand deterministic planning from repository survey facts, move durable latest-plan and observed-snapshot/pending state into tracked files, stamp retrieval against exact clean or dirty snapshots, invoke CodeWiki incremental surfaces after local diffing, and make every terminal target result reachable through the persisted orchestrator.

**Tech Stack:** Python 3.12+, Pydantic 2, Typer, PyYAML, SQLite FTS5, pytest, public CodeWiki 0.6 CLI only.

## Global Constraints

- Work directly on `main`; do not create branches or worktrees.
- Use only public CodeWiki CLI/MCP/HTTP contracts; never import provider internals or read its database.
- Never execute analyzed repository code, tests, installers, or hooks.
- Start every behavior change with a focused failing test and observe the expected failure.
- Preserve atomic manifest-last publication and byte-exact crash recovery.
- Stale, conflicted, invalid, and insufficient-evidence targets never enter default Agent context.
- Push each verified coherent task to `origin/main`.

---

### Task 1: Survey-driven multi-target planning

**Files:**
- Modify: `src/knowledge_compiler/planning/module.py`
- Test: `tests/planning/test_module_planning.py`
- Test: `tests/integration/test_primary_build.py`

**Interfaces:**
- Consumes: `RepositorySurvey.files`, `symbols`, `languages`, `graph_communities`, and `configuration_facts`.
- Produces: `plan_full_refresh(request, survey) -> KnowledgePlan` with one architecture target, one tech-stack target, and bounded stable module/flow/rule targets derived from distinct survey evidence groups.

- [x] Add a failing test with two graph communities and type-specific facts asserting more than five stable targets, distinct module IDs/seeds, and deterministic ordering.
- [x] Run `.venv/bin/pytest -q tests/planning/test_module_planning.py` and confirm the existing fixed-five planner fails the new assertions.
- [x] Implement deterministic target discovery with safe slugs, deduplication, a documented maximum target count, and fallbacks for sparse surveys.
- [x] Add an integration test proving the orchestrator persists and schedules every discovered target without fixture-specific IDs.
- [x] Run planning, contract, and primary-build suites; commit `feat: discover repository knowledge targets` and push.

### Task 2: Tracked latest plan and manifest lifecycle state

**Files:**
- Create: `src/knowledge_compiler/storage/lifecycle.py`
- Modify: `src/knowledge_compiler/storage/generation.py`
- Modify: `src/knowledge_compiler/orchestrator/store.py`
- Modify: `src/knowledge_compiler/building.py`
- Modify: `src/knowledge_compiler/incremental/updating.py`
- Modify: `src/knowledge_compiler/incremental/pending.py`
- Test: `tests/storage/test_lifecycle_state.py`
- Test: `tests/integration/test_primary_build.py`

**Interfaces:**
- Produces: atomic `save_latest_plan(root, plan, run)`, manifest `observed_snapshot`, and manifest `pending_targets` projections.
- Preserves: existing run-local `plan.json` and pending store as recoverable execution details; tracked files become durable cross-machine truth.

- [x] Add failing tests asserting `.knowledge/plan.yaml` exists after planning and records target state/result/published ID, and that manifest publication preserves exact observed snapshot plus pending target IDs.
- [x] Confirm tests fail because only `state/runs/*/plan.json` and `state/pending-targets.json` exist.
- [x] Implement strict lifecycle DTOs and atomic YAML writes; extend generation journals so manifest state participates in rollback/recovery.
- [x] Project run transitions and pending mutations into tracked state without storing source bodies or secrets.
- [x] Add crash tests at plan/manifest replacement boundaries and run storage/orchestrator/incremental suites.
- [x] Commit `feat: persist tracked lifecycle state` and push (follow-up hardening in `fix: make lifecycle mutations transactional`).

### Task 3: Exact clean and dirty snapshot retrieval gates

**Files:**
- Modify: `src/knowledge_compiler/retrieval/context.py`
- Modify: `src/knowledge_compiler/retrieval/store.py`
- Modify: `src/knowledge_compiler/compiler/wiki.py`
- Test: `tests/retrieval/test_context_retrieval.py`
- Test: `tests/integration/test_final_gate.py`

**Interfaces:**
- Consumes: manifest `observed_snapshot` containing repository ID, snapshot ID, commit, dirty flag, and working-tree hash.
- Produces: index meta with the same identity; `require_current_view` accepts clean or dirty repositories only when all fields match byte-for-byte.

- [ ] Add a failing test that builds/indexes a dirty snapshot, retrieves successfully while unchanged, then changes one eligible byte and expects `knowledge_update_required`.
- [ ] Confirm current code fails immediately on every dirty snapshot.
- [ ] Replace blanket dirty rejection with exact observed/index/current snapshot comparison; require non-null matching working-tree hashes when dirty.
- [ ] Rewrite the final lifecycle fixture to resolve the new committed snapshot rather than injecting the old fixture snapshot after a commit.
- [ ] Run retrieval, CLI, MCP, and final-gate suites; commit `fix: gate retrieval on exact snapshot identity` and push.

### Task 4: Real CodeWiki incremental hints and complete retirement proof

**Files:**
- Modify: `src/knowledge_compiler/providers/base.py`
- Modify: `src/knowledge_compiler/providers/codewiki.py`
- Modify: `src/knowledge_compiler/incremental/updating.py`
- Modify: `src/knowledge_compiler/incremental/retirement.py`
- Test: `tests/providers/test_codewiki_contract.py`
- Test: `tests/incremental/test_retirement.py`
- Test: `tests/integration/test_primary_build.py`

**Interfaces:**
- Produces: provider `sync_incremental(repo, changes)` and `affected(repo, changes)` DTOs invoked only after Knowledge Compiler computes its local ChangeSet.
- Produces: retirement proof that records exact symbol, path, graph-node, and lexical searches, completeness/limit status, and refreshed inbound relation results.

- [ ] Add failing adapter tests asserting `codewiki update` and `graph affected` occur after local diff creation and provider failure still leaves safe invalidation committed.
- [ ] Add failing retirement tests for truncated/inconclusive results, lexical-only matches, graph-node matches, and inbound relations that disappear only after refresh.
- [ ] Implement public CLI calls and normalized bounded DTOs; provider hints enrich but never replace local invalidation.
- [ ] Extend retirement checks so every required query class completes on the current snapshot; any unsupported/truncated/error result remains stale and pending.
- [ ] Run provider/incremental/security suites; commit `feat: use complete incremental evidence proofs` and push.

### Task 5: Reachable terminal results and generic validation

**Files:**
- Modify: `src/knowledge_compiler/contracts/semantic.py`
- Modify: `src/knowledge_compiler/workers/litellm_worker.py`
- Modify: `src/knowledge_compiler/orchestrator/runner.py`
- Modify: `src/knowledge_compiler/cli_agent_queue.py`
- Modify: `src/knowledge_compiler/cli.py`
- Test: `tests/orchestrator/test_runner.py`
- Test: `tests/cli/test_agent_queue.py`
- Test: `tests/cli/test_view_commands.py`

**Interfaces:**
- Produces: explicit insufficient-evidence extraction outcome, two persisted repair attempts with fresh leases/idempotency keys, and correct invalid/conflicted/insufficient/retired/skipped target results.
- Produces: repository-generic `knowledge validate` driven by manifest object inventory rather than fixture IDs.

- [ ] Add failing tests for malformed extraction repair, unsupported verification repair, exhausted repair terminal state, explicit insufficient evidence, retirement reflected in latest plan, and validation of arbitrary object IDs/types.
- [ ] Confirm current code marks failures directly invalid/conflicted and `knowledge validate` searches for `module.shop.checkout`.
- [ ] Implement the minimal terminal outcome contract and repair transitions while preserving extraction/verification context separation.
- [ ] Replace hard-coded validation paths with manifest-bound canonical/Card/Wiki checks and generation/index consistency checks.
- [ ] Run orchestrator, CLI, integration, and full offline suite twice; update README truthfully with the new count and remaining live/A-B limitation.
- [ ] Commit `fix: complete target lifecycle semantics` and push.

## Final verification

- [ ] Run `git diff --check` and compile `src` only.
- [ ] Run the full offline suite twice with identical results.
- [ ] Run one opt-in live CodeWiki/LiteLLM build only when credentials and model configuration are available; otherwise keep the limitation explicit.
- [ ] Run the final fixture lifecycle without stale snapshot injection.
- [ ] Record remaining M8 A/B benchmark work separately; do not claim product-effect validation from fixture tests.
