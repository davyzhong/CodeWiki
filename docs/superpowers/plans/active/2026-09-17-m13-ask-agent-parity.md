---
status: approved-not-started
last-reviewed: 2026-09-25
scope: local-beta-m13
sources:
  - docs/superpowers/specs/2026-09-17-local-beta-product-design.md
  - docs/superpowers/plans/active/2026-09-17-local-beta-master-plan.md
---

# M13 Ask and Agent Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Web Ask, CLI context/search, and MCP return the same Claim-level evidence under identical snapshot, filters, and budgets.

**Architecture:** Upgrade the rebuildable FTS projection from object rows to Claim rows, place retrieval/ranking in one application service, and adapt all transports to shared DTOs. Optional model summaries consume the retrieved evidence envelope and can never create unsupported claims.

**Tech Stack:** SQLite FTS5, Pydantic, shared Python services, FastAPI, Typer, MCP JSON-RPC, React, optional LiteLLM summarizer, parity/property tests.

---

### Task 1: Define Claim-level search contracts and relevance fixtures

**Files:**
- Create: `src/knowledge_compiler/contracts/search.py`
- Create: `tests/fixtures/search/relevance_cases.yaml`
- Test: `tests/contracts/test_search_contracts.py`
- Test: `tests/retrieval/test_relevance_cases.py`

- [ ] Define query, filters, budget, match reason, Claim hit, Evidence hit, related object, currentness, and pagination contracts.
- [ ] Add Chinese/English, path, type, exact symbol, rule, no-hit, stale, and injection-like query cases with expected ordered IDs.
- [ ] Run focused tests; expect missing contracts/index behavior.
- [ ] Implement contracts only; keep relevance failures visible for Task 2.
- [ ] Commit: `test: define claim search relevance contract`.

### Task 2: Migrate FTS projection to Claim granularity

**Files:**
- Modify: `src/knowledge_compiler/retrieval/store.py`
- Modify: `src/knowledge_compiler/retrieval/context.py`
- Create: `src/knowledge_compiler/retrieval/schema.py`
- Test: `tests/retrieval/test_claim_index.py`
- Test: `tests/retrieval/test_context_retrieval.py`

- [ ] Test schema versioning, atomic rebuild, Claim/evidence rows, field weighting, filters, phrase-safe terms, no-hit, generation mismatch, and rebuild from canonical objects.
- [ ] Run tests; expect failures under object-level schema.
- [ ] Implement Claim FTS with title/type/path fields and explicit relation expansion after primary ranking.
- [ ] Preserve `retrieve_task_context` public behavior while routing through Claim hits.
- [ ] Run retrieval/relevance tests; expect PASS.
- [ ] Commit: `feat: index and rank knowledge claims`.

### Task 3: Create one search/Ask/context application service

**Files:**
- Create: `src/knowledge_compiler/application/search.py`
- Create: `src/knowledge_compiler/application/context.py`
- Test: `tests/application/test_search_service.py`
- Test: `tests/application/test_context_service.py`

- [ ] Test deterministic evidence sets, budget accounting, include/exclude reasons, currentness gate, filters, related expansion, and stable serialization.
- [ ] Run focused tests; expect import failure.
- [ ] Implement services over retrieval modules; no transport may implement its own ranking.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: unify search ask and context services`.

### Task 4: Add Ask/search/context APIs and UI

**Files:**
- Create: `src/knowledge_compiler/app/routes/search.py`
- Create: `src/knowledge_compiler/app/routes/context.py`
- Create: `web/src/features/ask/AskPage.tsx`
- Create: `web/src/features/ask/SearchFilters.tsx`
- Create: `web/src/features/context/ContextPreview.tsx`
- Test: `tests/app/test_search_api.py`
- Test: `web/src/features/ask/__tests__/AskPage.test.tsx`
- Test: `web/e2e/ask.spec.ts`

- [ ] Test results, filters, highlighted match reason, citations, no coverage, stale rejection, budget display, copy, and API error actions.
- [ ] Implement evidence-only Ask as default; never present excerpts without object/claim/source identity.
- [ ] Run Python/frontend/E2E tests; expect PASS.
- [ ] Commit: `feat: add evidence-first ask and context preview`.

### Task 5: Add optional citation-enforced summarization

**Files:**
- Create: `src/knowledge_compiler/workers/answer_worker.py`
- Create: `src/knowledge_compiler/validation/answers.py`
- Modify: `src/knowledge_compiler/application/search.py`
- Test: `tests/workers/test_answer_worker.py`
- Test: `tests/validation/test_answer_validation.py`

- [ ] Test every material sentence carries known evidence IDs, unknown/unsupported citations fail, empty evidence never calls a model, and invalid summaries fall back to evidence-only.
- [ ] Test credentials and full repository paths are absent from prompts/results.
- [ ] Run focused tests; expect missing behavior.
- [ ] Implement an opt-in summarizer using configured LiteLLM profile and strict result validation.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: add citation-enforced optional answers`.

### Task 6: Refactor CLI and MCP onto shared services

**Files:**
- Modify: `src/knowledge_compiler/cli.py`
- Modify: `src/knowledge_compiler/mcp_server.py`
- Create: `src/knowledge_compiler/application/mcp_tools.py`
- Test: `tests/cli/test_view_commands.py`
- Test: `tests/mcp/test_server.py`
- Create: `tests/integration/test_surface_parity.py`

- [ ] Freeze current CLI/MCP backward-compatible outputs, then add parity assertions comparing canonical hit/evidence IDs across Python service, HTTP, CLI JSON, and MCP structured content.
- [ ] Run parity test; expect failure while transports rank independently.
- [ ] Refactor transports to shared services and stable DTO serializers.
- [ ] Add MCP capability/status/job-diagnostic read tools only if they reuse application services and remain read-only.
- [ ] Run focused and parity tests; expect PASS.
- [ ] Commit: `refactor: unify web cli and mcp knowledge access`.

### Task 7: Retrieval quality, latency, and usage evidence

**Files:**
- Create: `benchmark/retrieval_runner.py`
- Create: `benchmark/retrieval_cases.yaml`
- Create: `tests/benchmark/test_retrieval_runner.py`
- Create: `src/knowledge_compiler/application/usage.py`
- Test: `tests/application/test_usage_service.py`

- [ ] Define Recall@k, MRR, citation completeness, context utilization, cold/warm latency, token/character use, and optional model cost outputs.
- [ ] Test deterministic JSONL, redaction, disabled telemetry by default, and local-only usage history.
- [ ] Run dry benchmark twice; expect byte-equivalent summaries except declared timing fields.
- [ ] Commit: `test: add retrieval quality and usage evidence`.

### Task 8: M13 parity and documentation gate

**Files:**
- Create: `docs/materials/validation/m13/README.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `HANDOFF.md`

- [ ] Run parity tests on at least two external repositories and dirty/stale variants.
- [ ] Run retrieval quality benchmark, full verification, frontend checks, and link checks.
- [ ] Record evidence IDs from each surface, screenshots, metrics, and limitations.
- [ ] Update README and docs under D-027.
- [ ] Commit: `docs: close M13 ask and agent parity` and push `main`.
