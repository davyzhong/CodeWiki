---
status: approved-not-started
last-reviewed: 2026-09-25
scope: local-beta-m9-m14
sources:
  - docs/superpowers/specs/2026-09-17-local-beta-product-design.md
---

# CodeWiki Local Beta Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a trustworthy, zero-server local CodeWiki Beta for individual developers across Web, CLI, and MCP.

**Architecture:** Preserve `.knowledge/` as the repository authority and introduce a shared application-service layer used by a loopback FastAPI app, existing CLI, and MCP. Supervise the external parser behind a capability-aware process boundary, ship a compiled React UI inside the Python package, and keep SQLite/FTS/job tables as rebuildable projections rather than a second knowledge source.

**Tech Stack:** Python 3.12+, Pydantic 2, Typer, FastAPI, Uvicorn, SQLite/FTS5, React, TypeScript, Vite, Vitest, Testing Library, Playwright, pytest, LiteLLM, optional PorunC CodeWiki CLI.

---

**Status:** Approved planning baseline — implementation not started.  
**Specification:** [Local Beta Product Design](../../specs/2026-09-17-local-beta-product-design.md)  
**Visual design:** [Approved HTML](../../../design/2026-09-17-local-beta-design.html)  
**Branch policy:** work directly on `main`; do not create branches or worktrees.  
**Tracking rule:** check a step only after its stated command and expected result pass.

## 1. Plan suite and dependency order

| Milestone | Detailed plan | Depends on | Product proof |
| --- | --- | --- | --- |
| M9 | [Local product foundation](2026-09-17-m9-local-product-foundation.md) | V0.1 baseline | fresh-machine install opens empty local app |
| M10 | [Reliable repository parsing](2026-09-17-m10-reliable-repository-parsing.md) | M9 app/API skeleton | three external repos; parser crash is contained |
| M11 | [Build-job lifecycle](2026-09-17-m11-build-job-lifecycle.md) | M9, M10 | interrupted build resumes without deleting state |
| M12 | [Knowledge-reading Beta](2026-09-17-m12-knowledge-reading-beta.md) | M9, M11 read APIs | overview → claim → source within three interactions |
| M13 | [Ask and Agent parity](2026-09-17-m13-ask-agent-parity.md) | M10, M12 | Web/CLI/MCP return the same evidence set |
| M14 | [Value proof and Beta release](2026-09-17-m14-value-proof-beta-release.md) | M9–M13 | reproducible M8 result and install/upgrade release gate |

M9–M13 are sequential at their public contracts but may contain internal parallel work only when the detailed plan marks files as non-overlapping. M14 is never used to postpone correctness work discovered earlier.

## 2. Locked file architecture

### Python application core

- Create `src/knowledge_compiler/application/` for shared use cases and transport-neutral DTOs.
- Create `src/knowledge_compiler/app/` for loopback HTTP, job supervision, app SQLite, and packaged asset serving.
- Keep `src/knowledge_compiler/contracts/` authoritative for domain contracts; do not put HTTP models there.
- Keep `src/knowledge_compiler/storage/` authoritative for `.knowledge` transactions.
- Refactor CLI and MCP to call `application/`; they must not call HTTP over loopback.

### Frontend

- Create `web/` for React/TypeScript source and tests.
- Build to `src/knowledge_compiler/app/static/`; generated assets are wheel inputs and are not hand-edited.
- Keep deterministic export rendering separate from the live app. Static Wiki remains available and must not require JavaScript tooling at runtime.

### Tests and fixtures

- Mirror new Python packages under `tests/application/` and `tests/app/`.
- Put provider supervision tests under `tests/providers/`.
- Put frontend unit tests next to features in `web/src/**/__tests__/`.
- Put browser journeys in `web/e2e/`.
- Put external-repository smoke definitions in `tests/fixtures/real_repositories/`; never vendor third-party repository contents.

## 3. Cross-cutting contracts

- All API errors use `error.code`, `error.message`, `error.action`, and redacted `error.details`.
- Every job mutation accepts an idempotency key.
- Every read response includes repository ID, snapshot ID, and active generation where applicable.
- Capabilities are explicit data, not inferred by hiding buttons.
- Cancellation must terminate child process groups and persist a terminal state.
- No request handler performs long parsing/model work inline.
- No UI reads `.knowledge` files directly.
- No new store becomes a factual authority.
- Schema migrations and exports are deterministic and covered by golden tests.

## 4. Global verification gates

- [ ] Run focused tests after every task; expected result is the newly added test failing before implementation and passing after it.
- [ ] Run `VERIFY_FAST=1 bash scripts/verify.sh` before every milestone commit; expected result is all offline tests, compileall, diff-check, and audit gates passing.
- [ ] Run full `bash scripts/verify.sh` before declaring a milestone complete; expected result is two identical offline test counts and an explicit live-smoke result or skip reason.
- [ ] Run `pnpm --dir web test`, `pnpm --dir web build`, and the milestone's Playwright tests once `web/` exists.
- [ ] Run `python -m build` and install the wheel into a clean temporary virtual environment at M9 and M14.
- [ ] Run `python scripts/check_links.py` after every documentation update.
- [ ] Update `README.md`, `docs/README.md`, the active plan checkboxes, and `HANDOFF.md` at every milestone exit.
- [ ] Commit each green task directly on `main`, then push completed milestone work to `origin/main`.

## 5. Milestone exit review

For every M9–M14 exit, attach under `docs/materials/validation/<milestone>/`:

1. exact commit SHA and environment versions;
2. verification commands and outputs;
3. real-repository identifiers and snapshots;
4. screenshots for user-visible flows;
5. known limitations and deferred issues;
6. confirmation that README/doc indexes reflect the delivered state.

Do not mark the plan complete because code exists. Complete means product behavior, regression tests, real-repository evidence, docs, and remote `main` agree.

## 6. Final release definition

The Local Beta is releasable only when:

- all six detailed plans are fully checked;
- the full verification suite passes;
- installation, upgrade, backup/restore, and uninstall tests pass on macOS and Linux;
- parser crashes and model failures have verified recovery paths;
- Web, CLI, and MCP parity tests pass;
- M8 results are published whether positive or negative;
- README contains the shipped capabilities, limitations, screenshots, and benchmark conclusion;
- `git status --short --branch` is clean and `HEAD == origin/main`.
