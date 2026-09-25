---
status: active
last-reviewed: 2026-09-25
scope: project-freeze-and-closure-readiness
sources:
  - rules/principles.md P-002
  - docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md
  - docs/superpowers/specs/2026-09-17-local-beta-product-design.md
---

# Project Freeze and Closure Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not delegate unless the user explicitly requests subagents.

**Goal:** Determine, with reproducible evidence, whether CodeWiki is ready for a version freeze or full project closure, close every in-scope omission that can be closed safely, and preserve a complete static project archive.

**Architecture:** Treat the repository as three linked records: source and verification evidence, maintained static knowledge, and workflow history. Audit each approved promise against implementation and tests, compare only scope-relevant capabilities with current official competitor sources, then either close the remaining gaps or record an explicit freeze/closure blocker without expanding the product.

**Tech Stack:** Git, Python 3.12, pytest, Ruff-compatible source inspection, Playwright/browser screenshots, Markdown/YAML governance, GitHub official sources and product documentation.

---

**Execution policy:** work only on `main`; pull before each work session; verify before each commit; push immediately after every commit. Deletion, directory removal, schema migration, CI changes, dependency installation, rebase/reset, force push, and public release remain approval-gated.

## Locked outputs

- Create `docs/reviews/2026-09-25-project-closure-review.md`: authoritative review and closure verdict.
- Create `docs/materials/validation/project-freeze-2026-09-25/`: raw verification summaries, fresh UI screenshots, environment manifest, and inventory evidence.
- Create `docs/materials/archives/2026-09-25-project-freeze-manifest.md`: immutable archive manifest and exact commit pointers.
- Create `docs/knowledge/product/evolution.md`: maintained end-to-end project evolution.
- Create `docs/knowledge/product/traceability.md`: promise → implementation → test → evidence matrix.
- Update `README.md`, `README.en.md`, `HANDOFF.md`, `docs/README.md`, relevant knowledge pages, and the decision log so all status surfaces agree.

### Task 1: Freeze the audit baseline and closure semantics

**Files:**
- Modify: `docs/superpowers/plans/active/2026-09-25-project-freeze-closure-audit.md`
- Create: `docs/materials/validation/project-freeze-2026-09-25/environment.md`
- Create: `docs/knowledge/product/traceability.md`

- [ ] Record `HEAD`, Python/Node/tool versions, OS, dirty state, installed optional capabilities, and the exact verification commands.
- [ ] Enumerate every approved V0.1, M8, and Local Beta M9–M14 promise; classify each as shipped, implemented but unproven, planned only, blocked, cancelled, or out of scope.
- [ ] Verify classifications against source paths and tests; a plan or README sentence is never implementation evidence.
- [ ] Define two separate decisions: V0.1 freeze readiness and whole-project closure readiness.
- [ ] Run `python scripts/check_links.py`; expect `link check: PASS`.
- [ ] Commit and push the baseline evidence.

### Task 2: Run the complete engineering and repository audit

**Files:**
- Create: `docs/materials/validation/project-freeze-2026-09-25/engineering-audit.md`
- Modify: affected source/tests only when an in-scope defect is reproduced

- [ ] Run the full `bash scripts/verify.sh`; preserve the summary and any opt-in skip reason.
- [ ] Audit packaging, public commands, API/MCP contracts, deterministic outputs, recovery paths, dependency bounds, secret handling, unsafe repository execution, and generated-state exclusions.
- [ ] Scan for dead code, duplicated responsibilities, stale names, TODO/FIXME markers, untracked build outputs, large files, broken references, and docs that disagree with as-built behavior.
- [ ] Reproduce each suspected defect with a focused failing test before changing code.
- [ ] Fix only omissions already required by the approved scope; defer scope additions explicitly.
- [ ] Re-run focused tests and `VERIFY_FAST=1 bash scripts/verify.sh`; expect PASS.
- [ ] Commit and push each independently verified repair.

### Task 3: Capture and audit the real user-facing product

**Files:**
- Create: `docs/materials/validation/project-freeze-2026-09-25/ui/01-entry.png`
- Create: additional numbered screenshots under the same directory
- Create: `docs/materials/validation/project-freeze-2026-09-25/product-audit.md`

- [ ] Start the currently shipped product from documented commands in a clean temporary repository; do not treat the design HTML as shipped product.
- [ ] Capture fresh screenshots for entry, navigation, knowledge overview, object detail/evidence, Ask, history, empty/error states, and mobile reflow where those states exist.
- [ ] Inspect every saved screenshot before accepting it; record a named blocker for any unreachable flow.
- [ ] Review discoverability, hierarchy, consistency, trust states, keyboard/focus behavior, labels, contrast risks, reflow, error recovery, and source traceability.
- [ ] Separate confirmed visual findings from accessibility checks that require DOM/keyboard/assistive-technology testing.
- [ ] Commit and push accepted evidence and the audit.

### Task 4: Refresh the market comparison without expanding scope

**Files:**
- Create: `docs/materials/validation/project-freeze-2026-09-25/competitor-sources.md`
- Modify: `docs/knowledge/industry/landscape.md`
- Modify: `docs/knowledge/industry/patterns.md`
- Modify: `docs/knowledge/industry/upstream-codewiki.md`

- [ ] Re-verify official current sources for Qoder, DeepWiki, GitHub Copilot, Sourcegraph, Cursor, Augment, Greptile, Google Code Wiki, PorunC/CodeWiki, GitBook, and Backstage; add another product only when it materially overlaps the fixed scope.
- [ ] Compare repository ingestion, parser resilience, source grounding, update/invalidity semantics, knowledge model, human correction, navigation, Ask, Agent integration, local/privacy model, observability, export, and lifecycle.
- [ ] Assign every observed gap one disposition: `close before freeze`, `retain current design`, `blocked evidence`, or `out of scope`.
- [ ] Reject feature parity as a goal; recommendations must connect to an existing approved user outcome or closure risk.
- [ ] Add retrieval date and direct official URL for every externally changeable claim.
- [ ] Run link checks, then commit and push the refreshed knowledge.

### Task 5: Prepare a safe cleanup and migration ledger

**Files:**
- Create: `docs/materials/validation/project-freeze-2026-09-25/path-migration-map.md`
- Create: `docs/materials/validation/project-freeze-2026-09-25/cleanup-ledger.md`
- Modify: `.gitignore`

- [ ] List exact duplicate, stale, generated, orphaned, misnamed, and misplaced paths with size, references, owner, risk, and proposed disposition.
- [ ] Fix non-destructive hygiene issues such as missing ignores and stale live-document links.
- [ ] For every rename, preserve stable document IDs and map old path → new path before using `git mv`.
- [ ] Search all Markdown, frontmatter, manifests, scripts, README trees, and tests for each old path.
- [ ] Present the exact deletion/rename batch for user approval before executing any approval-gated filesystem change.
- [ ] After approval, execute the migration as an isolated commit, run link/test gates, and push immediately.

### Task 6: Complete the static knowledge base and evolution record

**Files:**
- Create: `docs/knowledge/product/evolution.md`
- Modify: `docs/materials/origin/timeline.md`
- Modify: `docs/materials/source-catalog.md`
- Modify: `docs/knowledge/system/architecture.md`
- Modify: `docs/knowledge/system/behavior-reference.md`
- Modify: `docs/knowledge/product/decision-log.md`
- Modify: `docs/README.md`

- [ ] Reconcile project origin, milestone commits, design changes, incidents, upstream findings, and current state into one maintained timeline with links to frozen source material.
- [ ] Ensure every material has provenance, retrieval date where relevant, license/redistribution note, and a maintained-knowledge destination or explicit archival-only disposition.
- [ ] Update as-built architecture and behavior from the current source tree, not from planned M9–M14 files.
- [ ] Consolidate active plans into one authoritative status view; mark completed/superseded/cancelled work without deleting historical records.
- [ ] Confirm all maintained knowledge pages have valid frontmatter and revision history.
- [ ] Run link checks and commit/push the knowledge-base closure.

### Task 7: Produce the closure review and archive manifest

**Files:**
- Create: `docs/reviews/2026-09-25-project-closure-review.md`
- Create: `docs/materials/archives/2026-09-25-project-freeze-manifest.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `HANDOFF.md`
- Modify: `docs/README.md`
- Modify: `docs/knowledge/product/decision-log.md`

- [ ] Summarize verified strengths, all in-scope omissions, competitor-derived optimizations, rejected scope expansion, cleanup results, known limitations, and exact evidence links.
- [ ] Issue independent verdicts for V0.1 freeze and whole-project closure: ready, conditionally ready, or not ready.
- [ ] If not ready, keep only bounded closure blockers in the active checklist; do not invent a new product roadmap.
- [ ] Record the complete archive tree, file hashes for critical artifacts, final test summary, external blockers, restore instructions, and final commit SHA.
- [ ] Synchronize README/HANDOFF/docs indexes and add the durable freeze decision to the decision log.
- [ ] Run `bash scripts/verify.sh`, `python scripts/check_links.py`, and `git diff --check`; expect PASS or a documented opt-in skip only.
- [ ] Commit, push, verify `git status --short --branch` is clean, and verify `HEAD == origin/main`.

## Final acceptance

- [ ] No claim of completion relies on a plan, mockup, old screenshot, or prior chat alone.
- [ ] Every recommendation is classified against the fixed scope.
- [ ] Every active plan has an explicit closure disposition.
- [ ] Static knowledge, evolution history, archive manifest, README, HANDOFF, and source agree.
- [ ] All safe in-scope repairs are complete; approval-gated actions are either approved and executed or listed as blockers.
- [ ] The final report makes it impossible to confuse “V0.1 frozen” with “Local Beta shipped” or “project closed”.
