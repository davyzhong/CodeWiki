---
status: approved-not-started
last-reviewed: 2026-09-25
scope: local-beta-m10
sources:
  - docs/superpowers/specs/2026-09-17-local-beta-product-design.md
  - docs/superpowers/plans/active/2026-09-17-local-beta-master-plan.md
---

# M10 Reliable Repository Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make repository parsing capability-aware, crash-contained, cancellable, diagnosable, and safely degradable across real Python, TypeScript, and C-family repositories.

**Architecture:** Extend the EvidenceProvider boundary with explicit capabilities and health, run PorunC CodeWiki only through a supervised process group, and add a limited local fallback provider whose degraded semantics are visible to every caller.

**Tech Stack:** Python subprocess/process groups, Pydantic contracts, existing git inventory, ripgrep-compatible lexical search, pytest fault injection, local API/React status UI.

---

### Task 1: Define provider capabilities and health contracts

**Files:**
- Modify: `src/knowledge_compiler/providers/base.py`
- Create: `src/knowledge_compiler/contracts/capabilities.py`
- Test: `tests/contracts/test_provider_capabilities.py`
- Modify: `tests/providers/test_fake_provider.py`

- [ ] Test capability serialization for languages, graph operations, incremental support, provider/version, and `ready|degraded|failed|unavailable` health.
- [ ] Test that `ensure_index` cannot return ready when mandatory capabilities are absent.
- [ ] Run focused tests; expect failures for missing models.
- [ ] Implement immutable contracts and add `capabilities()`/`health()` to provider protocols and fake provider.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: define evidence provider capabilities`.

### Task 2: Implement supervised child-process execution

**Files:**
- Create: `src/knowledge_compiler/providers/process_supervisor.py`
- Test: `tests/providers/test_process_supervisor.py`
- Create: `tests/support/process_behaviors.py`

- [ ] Test success, non-zero exit, SIGSEGV, timeout, oversized stdout/stderr, invalid UTF-8, cancellation, and descendant cleanup.
- [ ] Run the test file; expect module import failure.
- [ ] Implement process-group launch, bounded capture, monotonic timeout, TERM→KILL escalation, structured diagnostics, and secret redaction.
- [ ] Run focused tests repeatedly (`--count=5` when available); expect no leaked child processes.
- [ ] Commit: `feat: supervise external parser processes`.

### Task 3: Route the CodeWiki CLI adapter through supervision

**Files:**
- Modify: `src/knowledge_compiler/providers/codewiki_cli.py`
- Modify: `src/knowledge_compiler/providers/codewiki.py`
- Test: `tests/providers/test_codewiki_contract.py`
- Test: `tests/integration/test_real_provider_slice.py`

- [ ] Add failing tests mapping crash/timeout/version mismatch/malformed JSON to stable typed errors and health states.
- [ ] Assert no partial provider output is accepted as ready.
- [ ] Run focused tests; expect failure under the old raw subprocess runner.
- [ ] Replace execution with `ProcessSupervisor` while preserving public normalization and U3 evidence-ID behavior.
- [ ] Run focused and fixture integration tests; expect PASS.
- [ ] Commit: `fix: contain CodeWiki parser failures`.

### Task 4: Add a safe degraded evidence provider

**Files:**
- Create: `src/knowledge_compiler/providers/local_text.py`
- Test: `tests/providers/test_local_text_provider.py`
- Modify: `src/knowledge_compiler/providers/__init__.py`

- [ ] Test repository survey, bounded text search, exact evidence reads, exclusions, binary/oversize skipping, symlink refusal, deterministic IDs, and token/character budgets.
- [ ] Test that graph/affected capabilities are explicitly false and never fabricated.
- [ ] Run focused tests; expect import failure.
- [ ] Implement using `LocalGitRepositoryProvider` eligible files and safe source reads; do not execute repository code.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: add degraded local evidence provider`.

### Task 5: Add provider selection and degradation policy

**Files:**
- Create: `src/knowledge_compiler/application/providers.py`
- Modify: `src/knowledge_compiler/config.py`
- Modify: `src/knowledge_compiler/building.py`
- Test: `tests/application/test_provider_service.py`
- Test: `tests/cli/test_build.py`

- [ ] Test `strict`, `allow-degraded`, and explicit `local-text` policy; strict never silently falls back.
- [ ] Test that degraded builds carry diagnostics and cannot claim graph-derived completeness.
- [ ] Run focused tests; expect failures.
- [ ] Implement policy and propagate capability/health into build outcome and last-build report.
- [ ] Run focused tests; expect PASS with unchanged default fail-closed behavior until the user opts into degradation.
- [ ] Commit: `feat: add explicit provider degradation policy`.

### Task 6: Expose parse lifecycle and remediation in API/UI

**Files:**
- Create: `src/knowledge_compiler/app/routes/providers.py`
- Modify: `src/knowledge_compiler/app/routes/repositories.py`
- Create: `web/src/features/repositories/ProviderStatus.tsx`
- Create: `web/src/features/repositories/RepositoryPreflight.tsx`
- Test: `tests/app/test_provider_api.py`
- Test: `web/src/features/repositories/__tests__/ProviderStatus.test.tsx`
- Test: `web/e2e/provider-failure.spec.ts`

- [ ] Test ready/indexing/degraded/failed/unavailable states, plain-language impact, and retry/degraded actions.
- [ ] Test a simulated SIGSEGV leaves the Web app responsive and diagnostics downloadable.
- [ ] Implement routes and UI without hiding unavailable features.
- [ ] Run Python, frontend, and E2E focused tests; expect PASS.
- [ ] Commit: `feat: surface parser capability and recovery`.

### Task 7: Create external-repository smoke corpus

**Files:**
- Create: `tests/fixtures/real_repositories/python.yaml`
- Create: `tests/fixtures/real_repositories/typescript.yaml`
- Create: `tests/fixtures/real_repositories/c.yaml`
- Create: `scripts/run_repository_smoke.py`
- Create: `tests/integration/test_repository_smoke_manifest.py`
- Create: `docs/runbooks/2026-09-17-repository-smoke.md`

- [ ] Define immutable repository URL, commit, language, size ceiling, commands, and expected minimum capabilities; do not vendor source.
- [ ] Test manifest validation, clean temporary checkout, timeout, cleanup, and JSON result schema.
- [ ] Run manifest tests; expect PASS after implementation.
- [ ] Run the smoke script against all three pinned repos; save raw results outside source fixtures.
- [ ] Commit: `test: add real repository parser smoke corpus`.

### Task 8: M10 fault and documentation gate

**Files:**
- Create: `docs/materials/validation/m10/README.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `HANDOFF.md`

- [ ] Run crash, timeout, cancellation, degraded-provider, and three-repository smoke suites.
- [ ] Run full `bash scripts/verify.sh` and frontend checks; expect green or an explicit separately recorded upstream live skip.
- [ ] Record versions, snapshots, timing, capability matrix, crash evidence, screenshots, and limitations.
- [ ] Update README shipped status and upstream issue status; apply D-027.
- [ ] Commit: `docs: close M10 reliable repository parsing` and push `main`.
