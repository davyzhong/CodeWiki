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

- [x] Treat missing/corrupt baselines as a full refresh instead of a no-op.
- [x] Atomically invalidate canonical objects and remove stale Agent Cards;
  verified-only FTS row handling remains part of the Gate 7 index implementation.
- [x] Persist and retry pending targets even when the next diff is empty.
- [x] Selectively rebuild affected targets and retire only with deterministic proof.
- [x] Return update exit codes 0 complete, 1 failed, and 2 partial.
- [x] Deliver the protocol-pinned `/knowledge-update` Skill.
- [x] Cover safe invalidation, pending retry, selective rebuild, proof blocking,
  empty-generation retirement, interruption recovery, and both Skill protocols;
  run the full suite (603 passed, 1 opt-in live test skipped).

## Gate 6 — Human overlay runtime semantics

- [x] Validate overlays before build/update without modifying them.
- [x] Apply supplements and overrides only at compilation/retrieval boundaries;
  retrieval-side application lands with the Gate 7 ContextRetriever.
- [x] Produce a conflicted target when changed machine evidence intersects an override.
- [x] Archive retired overlays byte-identically and recover safely after interruption.
- [x] Cover read-only validation, Markdown-only overlay merging with pure canonical
  IR, conflicted-target preservation of the previous generation and overlay bytes,
  byte-identical retirement archive inside the publication transaction, archive
  collision fail-closed, and interruption recovery; run the full suite
  (620 passed, 1 opt-in live test skipped).

## Gate 7 — Views, retrieval, and CLI

- [x] Compile complete deterministic Markdown Wiki, Cards, source index,
  Mermaid, and standalone HTML: per-object pages moved to type directories
  with stale expiry banners and orphaned-archive warnings, aggregate
  architecture/rules/tech-stack pages embed Mermaid plus rendered SVG,
  sources index cites evidence per object, the standalone HTML carries
  navigation/search/freshness metadata, publication leaves
  `wiki_generation` behind until `knowledge compile` succeeds, builds
  compile views after the canonical commit and report `partial` on view
  failure, and `open` warns on the lagging stamp
  (632 passed, 1 opt-in live test skipped at this checkpoint).
- [x] Build a generation-stamped verified-only SQLite FTS5 index and the
  budgeted one-hop ContextRetriever: `knowledge compile` and successful
  builds rebuild `.knowledge/cache/knowledge-index.sqlite3` from verified
  canonical objects only, retrieval fails closed with
  `knowledge_update_required` unless manifest stamps, index stamps, and
  the repository snapshot (commit + cleanliness) all agree, ranking is
  type-aware, one-hop relations join with attribution, human overlays
  surface as `source: human`, budgets are honored, and `--include-stale`
  stays a visibly marked diagnostic mode
  (639 passed, 1 opt-in live test skipped at this checkpoint).
- [x] Make `compile`, `context`, `open`, `serve`, and `status` perform
  their final specified behavior: compile publishes deterministic views
  plus the verified index, context serves budgeted retrieval in markdown
  or JSON, open warns on a lagging Wiki before opening, serve exposes
  the compiled HTML through a loopback-only read-only single-document
  server, and status reports canonical objects, view generations, and
  the latest run's target results separately
  (643 passed, 1 opt-in live test skipped at this checkpoint).

## Gate 8 — MCP and security

- [x] Implement exactly the seven read-only tools named in the V0.1
  design over a dependency-free stdio JSON-RPC server
  (`knowledge-mcp` console entry): repo overview, search, get object,
  get related, get evidence, context for task, and status.
- [x] Apply path, symlink, size, generation, credential, and injection
  boundaries to every tool: default reads fail closed on snapshot or
  generation mismatch, evidence answers only known Evidence IDs recorded
  in committed packs, arguments are bounds-checked, human and repository
  text is escaped as data, and include_stale stays a visibly marked
  diagnostic mode.
- [x] Prove MCP never builds, updates, writes canonical state, or
  executes repository code: a full seven-tool battery leaves the
  repository tree byte-identical, and the server module contains no
  build, publication, or subprocess path
  (651 passed, 1 opt-in live test skipped at this checkpoint).

## Final technical gate

- [ ] Run the full suite twice without network or paid models.
- [ ] Run CLI, MCP, security, crash-recovery, deterministic-output, and boundary matrices.
- [ ] Demonstrate one complete fixture build, incremental update, recovery, and context retrieval.
- [ ] Synchronize README, design status, handoff, sample `.knowledge/`, and `origin/main`.
- [ ] Start M8 benchmark work only after every technical gate above passes.
