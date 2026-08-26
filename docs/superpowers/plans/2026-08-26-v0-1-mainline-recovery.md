# CodeWiki V0.1 Mainline Recovery Plan

**Status:** Approved by the user; execution started 2026-08-26

**Goal:** Restore the approved V0.1 product path from real repository evidence through five-type generation, incremental lifecycle, protected human knowledge, compiled views, retrieval, and exactly seven read-only MCP tools.

**Execution policy:** Work directly on `main`. Start every behavior change with a failing focused test, make one coherent commit per task, run the full deterministic suite and boundary checks, and push reviewed work to `origin/main` after each completed gate.

## Gate 1 — Product CLI truthfulness

- [x] Register the design command names `compile`, `context`, and `open`.
- [x] Remove placeholder success behavior when required state is absent.
- [x] Scope build run state and reports to `--repository-root`.
- [x] Add focused CLI regression tests and run the full suite (557 passed).
- [x] Commit and push `060d360`.

## Gate 2 — Atomic multi-object generation

- [x] Add a failing test publishing at least two different object types in one generation.
- [x] Replace per-object publication with one precompiled, journaled generation transaction.
- [x] Preserve manifest-last commit, byte-exact replay, N+1 rollback, and recovery idempotency.
- [x] Prove removal and replacement of a complete generation cannot expose a mixed tree.
- [x] Switch RunOrchestrator publication ownership to the batch transaction.
- [x] Run storage/orchestrator focused suites (104 passed) and the full suite (561 passed).
- [x] Commit and push `ddb1f63`.

## Gate 3 — Generic persisted orchestrator

- [x] Remove Module/Checkout-specific target construction and canonicalization.
- [x] Persist EvidencePack and extraction request/result envelopes required for resume.
- [x] Repair the circular import that reduced `ExtractionResult.draft` to Module-only.
- [x] Persist planner topic, knowledge type, and evidence seeds on every run target.
- [x] Drive Architecture, Module, Flow, Rule, and TechStack through one state machine.
- [x] Publish all successful targets through the Gate 2 batch transaction.
- [x] Prove process-restart semantic verification and a five-target atomic generation.
- [x] Run focused contracts/validation/orchestrator suites (243 passed) and the full suite (569 passed).
- [x] Commit and push `456da0e` and `3786540`.

## Gate 4 — Real primary build

- [x] Wire LocalGit, public CodeWiki, five-type Planner, LiteLLM/Agent worker, Validator, and RunOrchestrator into `knowledge build`.
- [x] Honor `--executor llm|agent`, repository configuration, user-level model resolution, and exit 0/1/2 semantics.
- [x] Keep FakeEvidenceProvider limited to tests and explicit fixture demonstrations.
- [x] Persist plan, Evidence Packs, extraction context, verified canonical artifacts, and resume the active run across process/publication interruption.
- [x] Replace placeholder Agent submissions with contract-valid extraction/verification requests, multi-target scheduling, atomic final publication, and a complete run report.
- [x] Add offline contract/integration coverage and an explicit opt-in live CodeWiki/LiteLLM test.
- [x] Run focused CLI/integration/orchestrator suites and the full suite (583 passed, 1 opt-in live test skipped).
- [x] Commit and push `d9cfca7` and `c2011cb`.

## Gate 5 — Incremental lifecycle

- [ ] Treat missing/corrupt baselines as a full refresh instead of a no-op.
- [ ] Atomically invalidate canonical objects and remove stale Agent Cards/FTS rows.
- [ ] Persist and retry pending targets even when the next diff is empty.
- [ ] Selectively rebuild affected targets and retire only with deterministic proof.
- [ ] Return update exit codes 0 complete, 1 failed, and 2 partial.
- [ ] Deliver the protocol-pinned `/knowledge-update` Skill.

## Gate 6 — Human overlay runtime semantics

- [ ] Validate overlays before build/update without modifying them.
- [ ] Apply supplements and overrides only at compilation/retrieval boundaries.
- [ ] Produce a conflicted target when changed machine evidence intersects an override.
- [ ] Archive retired overlays byte-identically and recover safely after interruption.

## Gate 7 — Views, retrieval, and CLI

- [ ] Compile complete deterministic Markdown Wiki, Cards, source index, Mermaid, and standalone HTML.
- [ ] Build a generation-stamped verified-only SQLite FTS5 index.
- [ ] Implement budgeted one-hop ContextRetriever with snapshot/generation fail-closed checks.
- [ ] Make `compile`, `context`, `open`, `serve`, and `status` perform their final specified behavior.

## Gate 8 — MCP and security

- [ ] Implement exactly the seven read-only tools named in the V0.1 design.
- [ ] Apply path, symlink, size, generation, credential, and injection boundaries to every tool.
- [ ] Prove MCP never builds, updates, writes canonical state, or executes repository code.

## Final technical gate

- [ ] Run the full suite twice without network or paid models.
- [ ] Run CLI, MCP, security, crash-recovery, deterministic-output, and boundary matrices.
- [ ] Demonstrate one complete fixture build, incremental update, recovery, and context retrieval.
- [ ] Synchronize README, design status, handoff, sample `.knowledge/`, and `origin/main`.
- [ ] Start M8 benchmark work only after every technical gate above passes.
