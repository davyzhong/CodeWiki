---
status: approved-not-started
last-reviewed: 2026-09-25
scope: local-beta-m14
sources:
  - docs/superpowers/specs/2026-09-17-local-beta-product-design.md
  - docs/superpowers/plans/active/2026-09-17-local-beta-master-plan.md
  - docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md
---

# M14 Value Proof and Local Beta Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible product-value evidence and a locally installable Beta with verified upgrade, recovery, performance, security, and documentation behavior.

**Architecture:** Execute the already frozen M8 experiment after technical preconditions pass, add product-level fault/performance matrices around the shipped local app, and release only from a clean wheel installed in isolated environments.

**Tech Stack:** Existing benchmark harness, pytest, Playwright, wheel/build tooling, pip-audit, macOS/Linux CI, JSONL/Markdown reports.

---

### Task 1: Audit and freeze Beta release criteria

**Files:**
- Create: `docs/superpowers/specs/2026-09-17-local-beta-release-criteria.md`
- Modify: `docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md`
- Create: `tests/test_release_criteria.py`

- [ ] Encode machine-readable thresholds for required suites, supported platforms, migration versions, parser smoke, surface parity, accessibility, performance ceilings, and known-limit documentation.
- [ ] Keep M8 H1/H2 thresholds unchanged; record only newly satisfied technical preconditions.
- [ ] Run the criteria test; expect failure until all evidence paths exist.
- [ ] Commit: `docs: freeze local beta release criteria`.

### Task 2: Finalize real M8 task manifest

**Files:**
- Create: `benchmark/tasks.d/click.yaml`
- Create: `benchmark/tasks.d/flask.yaml`
- Create: `benchmark/tasks.d/requests.yaml`
- Modify: `benchmark/tasks.py`
- Test: `tests/benchmark/test_real_task_manifests.py`

- [ ] Pin 15 qualifying issues/tasks across three repositories to immutable base commits with machine-checkable tests and no external service dependency.
- [ ] Validate licensing, checkout, precondition failure, expected failing test, success test, and duplicate task IDs.
- [ ] Run manifest validation and a no-model preparation dry run; expect all 15 eligible or document frozen substitutions.
- [ ] Commit: `test: freeze real M8 task set`.

### Task 3: Execute and publish M8 A/B

**Files:**
- Modify: `benchmark/runner.py`
- Modify: `benchmark/stats.py`
- Create: `benchmark/results/<run-id>/raw.jsonl`
- Create: `benchmark/results/<run-id>/summary.json`
- Create: `docs/materials/validation/m14/m8-report.md`

- [ ] Confirm API key and user-approved cost ceiling without persisting credentials.
- [ ] Build knowledge once per pinned repository snapshot and record build failures separately.
- [ ] Run Control and Treatment-A for three seeds under the frozen backend/model/budget.
- [ ] Verify pair balance, diff hashes, logs, token/cost fields, and no `.knowledge` contamination.
- [ ] Produce H1/H2 statistics and publish the conclusion whether supported or not.
- [ ] Commit only redacted results allowed by repository policy: `benchmark: publish M8 product value result`.

### Task 4: Performance and resource envelope

**Files:**
- Create: `benchmark/product_performance.py`
- Create: `tests/benchmark/test_product_performance.py`
- Create: `docs/materials/validation/m14/performance.md`

- [ ] Measure cold install/start, repository registration, full/incremental parse, build, compile, overview, Claim search, Ask, context preview, memory, disk, and shutdown.
- [ ] Test small/medium repositories and explicit budget exceedance; record hardware and snapshots.
- [ ] Fail release criteria on unexplained regressions beyond frozen ceilings.
- [ ] Commit: `perf: establish local beta resource envelope`.

### Task 5: Product fault-injection matrix

**Files:**
- Create: `tests/integration/test_beta_fault_matrix.py`
- Create: `docs/materials/validation/m14/fault-matrix.md`

- [ ] Cover parser crash/timeout, model timeout/malformed result, disk full, permission error, SQLite corruption, app kill, worker kill, network loss, browser disconnect, dirty repo, repository deletion, stale generation, and invalid migration.
- [ ] Assert each case preserves authority, reports stable code/action, and either recovers or stops safely.
- [ ] Run matrix repeatedly; expect deterministic terminal classifications.
- [ ] Commit: `test: enforce local beta fault recovery`.

### Task 6: Install, upgrade, backup/restore, and uninstall

**Files:**
- Create: `scripts/release_smoke.py`
- Create: `tests/integration/test_beta_installation.py`
- Create: `docs/runbooks/2026-09-17-backup-restore.md`
- Create: `docs/runbooks/2026-09-17-upgrade-uninstall.md`

- [ ] Test clean wheel install on Python 3.12 and 3.13, packaged UI, first launch, previous supported app DB migration, repository-state compatibility, backup restore, uninstall preserving repository knowledge, and reinstall.
- [ ] Run on macOS and Linux CI plus one clean local macOS environment.
- [ ] Assert no Node runtime is required after wheel installation.
- [ ] Commit: `test: verify local beta lifecycle`.

### Task 7: Security, accessibility, and supply-chain release audit

**Files:**
- Modify: `scripts/verify.sh`
- Create: `docs/materials/validation/m14/security-accessibility.md`
- Modify: `.github/workflows/ci.yml` (create if absent)

- [ ] Run pip audit, frontend dependency audit, secret scan, path/symlink suites, loopback-binding test, diagnostics redaction, CSP/static asset checks, browser accessibility, and keyboard journeys.
- [ ] Triage every finding; no critical/high issue ships, and accepted lower risks require documented rationale.
- [ ] Make release CI execute the same commands as the runbook.
- [ ] Commit: `ci: add local beta release audit gate`.

### Task 8: Final documentation, package, and remote-main gate

**Files:**
- Create: `CHANGELOG.md`
- Create: `docs/runbooks/2026-09-17-local-beta.md`
- Create: `docs/materials/validation/m14/README.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `HANDOFF.md`
- Modify: `pyproject.toml`

- [ ] Update README from planned to shipped behavior, replace design-only images with verified product screenshots, and publish the M8 conclusion and limitations.
- [ ] Update all D-027 surfaces and mark completed plans historical without deleting audit history.
- [ ] Run `bash scripts/verify.sh`, all frontend/E2E checks, link checks, release criteria, wheel install, and clean-tree checks.
- [ ] Verify `git status --short --branch` is clean after commit and `git rev-parse HEAD` equals `git ls-remote origin refs/heads/main` after push.
- [ ] Commit: `release: publish CodeWiki local beta` and push `main`.
