# M11 Build Job Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give users a complete, observable, cancellable, resumable build/update workflow without weakening existing queue, validation, or publication guarantees.

**Architecture:** Wrap the existing persisted run queue in application-level job services and a supervised worker process. Project job/event summaries into app SQLite for UI speed, but rebuild them from `.knowledge/state/runs` whenever projections are missing or inconsistent.

**Tech Stack:** Existing RunQueue/RunStore, Python worker subprocess, SQLite projection, FastAPI/SSE, React task center, pytest/Playwright.

---

### Task 1: Define job and event contracts

**Files:**
- Create: `src/knowledge_compiler/application/jobs.py`
- Create: `src/knowledge_compiler/contracts/jobs.py`
- Test: `tests/contracts/test_job_contracts.py`
- Test: `tests/application/test_job_service.py`

- [ ] Test states `queued|planning|indexing|extracting|verifying|publishing|partial|complete|failed|cancelled|recovery_required` and legal transitions.
- [ ] Test progress counts, cost/token estimates, stable error codes, repository/snapshot/generation identity, and idempotency keys.
- [ ] Run focused tests; expect missing-contract failure.
- [ ] Implement immutable contracts and transport-neutral service interface.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: define local build job contracts`.

### Task 2: Add reconstructable job/event projection

**Files:**
- Add: `src/knowledge_compiler/app/migrations/002_job_projection.sql`
- Create: `src/knowledge_compiler/app/job_projection.py`
- Test: `tests/app/test_job_projection.py`

- [ ] Test append-only event sequence, per-job monotonic revisions, duplicate event idempotency, concurrent readers, WAL recovery, and projection rebuild from RunStore.
- [ ] Run focused tests; expect failure.
- [ ] Implement projection writes as post-state-change effects; failure to project must not corrupt canonical run state.
- [ ] Run tests with forced database interruption; expect successful rebuild.
- [ ] Commit: `feat: add rebuildable job event projection`.

### Task 3: Extract build/update application services

**Files:**
- Create: `src/knowledge_compiler/application/builds.py`
- Modify: `src/knowledge_compiler/building.py`
- Modify: `src/knowledge_compiler/incremental/updating.py`
- Modify: `src/knowledge_compiler/cli.py`
- Test: `tests/application/test_build_service.py`
- Test: `tests/cli/test_build_green_path.py`
- Test: `tests/cli/test_update.py`

- [ ] Write parity tests proving CLI build/update and application service produce the same outcome, diagnostics, generation, and exit classification.
- [ ] Run focused tests; expect service import failure.
- [ ] Move orchestration selection into services while keeping domain functions independent of HTTP/app SQLite.
- [ ] Run focused tests; expect PASS and unchanged CLI output contracts.
- [ ] Commit: `refactor: share build and update application services`.

### Task 4: Implement job worker supervision and controls

**Files:**
- Create: `src/knowledge_compiler/app/job_worker.py`
- Create: `src/knowledge_compiler/app/job_supervisor.py`
- Test: `tests/app/test_job_supervisor.py`

- [ ] Test one active mutation per repository, queued jobs across repositories, pause-at-safe-boundary, resume, cancel, crash, app restart, stale worker PID, and idempotent replay.
- [ ] Test cancellation during external parser and model calls terminates descendants and leaves recoverable run state.
- [ ] Run tests; expect missing module.
- [ ] Implement supervisor with explicit process ownership and event emission.
- [ ] Run focused tests; expect PASS without leaked processes.
- [ ] Commit: `feat: supervise local build jobs`.

### Task 5: Add knowledge-plan and build APIs

**Files:**
- Create: `src/knowledge_compiler/application/plans.py`
- Create: `src/knowledge_compiler/app/routes/plans.py`
- Create: `src/knowledge_compiler/app/routes/jobs.py`
- Test: `tests/app/test_plan_api.py`
- Test: `tests/app/test_job_api.py`

- [ ] Test plan preview, template, notes, page allowlist/tree, include/exclude, target count, evidence budgets, worker profile, estimated calls, and validation errors.
- [ ] Test create/list/detail/events/pause/resume/cancel/retry with idempotency headers.
- [ ] Run focused tests; expect 404.
- [ ] Implement routes; mutations enqueue work and return immediately.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: expose knowledge plan and job lifecycle API`.

### Task 6: Build planning and task-center UI

**Files:**
- Create: `web/src/features/build/KnowledgePlanPage.tsx`
- Create: `web/src/features/build/BuildTaskCenter.tsx`
- Create: `web/src/features/build/BuildDetailPage.tsx`
- Create: `web/src/features/build/jobState.ts`
- Test: `web/src/features/build/__tests__/KnowledgePlanPage.test.tsx`
- Test: `web/src/features/build/__tests__/BuildTaskCenter.test.tsx`
- Test: `web/e2e/build-lifecycle.spec.ts`

- [ ] Test plan editing, invalid scope, cost unknown, event reconnect, target progress, partial results, failure action, pause/resume/cancel confirmation, and app restart recovery.
- [ ] Run frontend tests; expect failures.
- [ ] Implement SSE with revision resume and polling fallback; never infer completion from connection close.
- [ ] Run unit/type/build/E2E; expect PASS.
- [ ] Commit: `feat: add knowledge planning and task center`.

### Task 7: Integrate overlays, history, and rollback safety

**Files:**
- Create: `src/knowledge_compiler/application/history.py`
- Create: `src/knowledge_compiler/app/routes/history.py`
- Modify: `src/knowledge_compiler/human/conflicts.py`
- Test: `tests/application/test_history_service.py`
- Test: `tests/app/test_history_api.py`

- [ ] Test generation list/diff, overlay conflicts, archived overlays, compile retry, and rollback metadata without allowing rollback to overwrite newer repository evidence.
- [ ] Run focused tests; expect failures.
- [ ] Implement read/diff and safe recovery actions; keep canonical publication in storage layer.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: expose auditable knowledge history`.

### Task 8: M11 recovery matrix and documentation gate

**Files:**
- Create: `tests/integration/test_local_job_recovery.py`
- Create: `docs/materials/validation/m11/README.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `HANDOFF.md`

- [ ] Implement fault injection at every Plan/Evidence/Extract/Verify/Publish boundary plus app/worker restart and projection corruption.
- [ ] Run the recovery matrix; expect prior committed generation preserved or the new generation atomically committed—never a mixed state.
- [ ] Run full Python/frontend verification and link checks.
- [ ] Record screenshots and exact recovery results; update D-027 surfaces.
- [ ] Commit: `docs: close M11 build job lifecycle` and push `main`.

