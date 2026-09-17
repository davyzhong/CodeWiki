# M12 Knowledge Reading Beta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an accessible local knowledge-reading experience that makes architecture, claims, sources, gaps, freshness, conflicts, and history understandable without exposing implementation IDs by default.

**Architecture:** Build read-model application services over canonical objects and existing compiler helpers, then expose stable API resources to a React information architecture. Keep deterministic static exports, but split the current monolithic Wiki compiler into focused renderers as behavior is touched.

**Tech Stack:** Python read models/FastAPI, React Router, TypeScript, SVG/Mermaid-safe diagrams, Vitest/Testing Library, Playwright/axe-style accessibility checks.

---

### Task 1: Define knowledge read models and navigation tree

**Files:**
- Create: `src/knowledge_compiler/application/knowledge.py`
- Create: `src/knowledge_compiler/contracts/read_models.py`
- Test: `tests/application/test_knowledge_service.py`

- [ ] Test overview counts, verified/insufficient/stale/retired/conflicted/degraded states, page hierarchy, object summaries, related objects, and stable sort order.
- [ ] Test raw IDs remain available in audit metadata but human labels are primary.
- [ ] Run focused tests; expect missing modules.
- [ ] Implement read models sourced only from canonical manifest/objects/plan/overlays.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: add knowledge reading models`.

### Task 2: Split Wiki compiler responsibilities without output drift

**Files:**
- Create: `src/knowledge_compiler/compiler/wiki_models.py`
- Create: `src/knowledge_compiler/compiler/wiki_pages.py`
- Create: `src/knowledge_compiler/compiler/wiki_site.py`
- Create: `src/knowledge_compiler/compiler/wiki_assets.py`
- Modify: `src/knowledge_compiler/compiler/wiki.py`
- Test: `tests/compiler/test_wiki_compilation.py`
- Create: `tests/compiler/test_wiki_golden_outputs.py`

- [ ] Freeze representative current outputs as normalized golden hashes after confirming no volatile paths.
- [ ] Run golden tests; expect PASS before refactor.
- [ ] Move one responsibility at a time; run the golden test after each move.
- [ ] Keep `compile_repository_wiki` public signature and deterministic bytes unchanged.
- [ ] Run compiler and integration suites; expect zero output drift.
- [ ] Commit: `refactor: split deterministic wiki compiler`.

### Task 3: Expose overview, tree, object, claim, evidence, and source APIs

**Files:**
- Create: `src/knowledge_compiler/app/routes/knowledge.py`
- Test: `tests/app/test_knowledge_api.py`
- Test: `tests/app/test_source_api_security.py`

- [ ] Test `/overview`, `/tree`, `/objects/{id}`, `/claims/{id}`, `/evidence/{id}`, `/sources`, and currentness metadata.
- [ ] Test path traversal, symlinks, dirty snapshots, retired/stale objects, unknown IDs, and line-range bounds.
- [ ] Run focused tests; expect 404.
- [ ] Implement read-only routes with stable ETags derived from snapshot/generation.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: expose trustworthy knowledge read API`.

### Task 4: Build application shell and repository overview

**Files:**
- Create: `web/src/app/router.tsx`
- Create: `web/src/app/AppShell.tsx`
- Create: `web/src/features/overview/OverviewPage.tsx`
- Create: `web/src/components/StatusBadge.tsx`
- Create: `web/src/components/EmptyState.tsx`
- Test: `web/src/features/overview/__tests__/OverviewPage.test.tsx`
- Test: `web/e2e/overview.spec.ts`

- [ ] Test responsive sidebar, currentness banner, coverage, gaps, recent changes, quick actions, empty/partial/degraded states, and audit drawer.
- [ ] Implement the approved IA and keep raw hashes out of the default hierarchy.
- [ ] Run unit/type/build/E2E; expect PASS.
- [ ] Commit: `feat: add repository overview experience`.

### Task 5: Build knowledge tree and typed object pages

**Files:**
- Create: `web/src/features/knowledge/KnowledgeMapPage.tsx`
- Create: `web/src/features/knowledge/ObjectPage.tsx`
- Create: `web/src/features/knowledge/ClaimCard.tsx`
- Create: `web/src/features/knowledge/EvidencePanel.tsx`
- Create: `web/src/features/knowledge/RelationList.tsx`
- Test: `web/src/features/knowledge/__tests__/ObjectPage.test.tsx`
- Test: `web/e2e/claim-to-source.spec.ts`

- [ ] Test architecture/module/flow/rule/tech-stack variants, missing evidence, multiple evidence refs, related objects, source permalink, and keyboard disclosure behavior.
- [ ] Implement route-preserving tree selection and three-interaction overview→claim→source flow.
- [ ] Run frontend checks; expect PASS.
- [ ] Commit: `feat: add knowledge map and evidence pages`.

### Task 6: Build sources, history, and diff experiences

**Files:**
- Create: `web/src/features/sources/SourcesPage.tsx`
- Create: `web/src/features/history/HistoryPage.tsx`
- Create: `web/src/features/history/GenerationDiffPage.tsx`
- Test: `web/src/features/history/__tests__/GenerationDiffPage.test.tsx`
- Test: `web/e2e/history.spec.ts`

- [ ] Test source→claims reverse lookup, generation timeline, added/changed/retired objects, overlay conflict, empty history, and unavailable old source lines.
- [ ] Implement human summaries first and raw diff/audit details on demand.
- [ ] Run checks; expect PASS.
- [ ] Commit: `feat: add source and generation history views`.

### Task 7: Accessibility, responsiveness, and visual regression

**Files:**
- Create: `web/e2e/accessibility.spec.ts`
- Create: `web/e2e/responsive.spec.ts`
- Create: `web/e2e/visual.spec.ts`
- Modify: `web/src/styles/tokens.css`
- Modify: `web/src/styles/global.css`

- [ ] Add automated checks for landmarks, headings, accessible names, focus order, contrast, keyboard-only operation, reduced motion, 320px width, 200% zoom, and long Chinese/English IDs.
- [ ] Capture approved desktop/mobile snapshots for overview, object, source, history, partial, and degraded states.
- [ ] Fix violations without hiding diagnostic content.
- [ ] Run all browser tests; expect PASS with reviewed snapshots.
- [ ] Commit: `test: enforce local web accessibility and visuals`.

### Task 8: M12 usability and documentation gate

**Files:**
- Create: `docs/materials/validation/m12/README.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `HANDOFF.md`

- [ ] Run a scripted task on an external repository: locate architecture → open claim → reach exact source; record interaction count and result.
- [ ] Run all Python/frontend/E2E/verification/link checks.
- [ ] Replace README future mockups with clearly labeled shipped screenshots while retaining design history.
- [ ] Record limitations and apply D-027.
- [ ] Commit: `docs: close M12 knowledge reading beta` and push `main`.

