# M9 Local Product Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package CodeWiki as a one-command local application with stable paths, repository registration, loopback API, packaged Web shell, preflight, and redacted diagnostics.

**Architecture:** Add transport-neutral application services first, then expose them through FastAPI and a bundled React SPA. Canonical repository data stays in `.knowledge`; an application SQLite database stores only repository registry and operational projections.

**Tech Stack:** Python, Pydantic, Typer, FastAPI/Uvicorn, platformdirs, SQLite, React/TypeScript/Vite, Vitest, Playwright, pytest/httpx.

---

### Task 1: Freeze packaging and runtime dependency contracts

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/app/test_packaging_contract.py`
- Create: `web/package.json`
- Create: `web/pnpm-lock.yaml`
- Create: `web/tsconfig.json`
- Create: `web/vite.config.ts`

- [ ] Write a failing test asserting `knowledge app` is registered, FastAPI/Uvicorn/platformdirs are runtime dependencies, and `knowledge_compiler/app/static/index.html` is wheel package data.
- [ ] Run `pytest tests/app/test_packaging_contract.py -v`; expect failure for missing app entry point and assets.
- [ ] Add bounded Python dependencies, package-data configuration, `knowledge-app`/`knowledge app` entry wiring, and pinned frontend scripts: `test`, `build`, `typecheck`, `e2e`.
- [ ] Run the focused test; expect PASS.
- [ ] Run `pnpm --dir web install --frozen-lockfile`; expect a reproducible install with no lockfile mutation.
- [ ] Commit: `build: define local app packaging contract`.

### Task 2: Add application paths and versioned app database

**Files:**
- Create: `src/knowledge_compiler/application/__init__.py`
- Create: `src/knowledge_compiler/application/paths.py`
- Create: `src/knowledge_compiler/app/db.py`
- Create: `src/knowledge_compiler/app/migrations/001_initial.sql`
- Create: `tests/application/test_paths.py`
- Create: `tests/app/test_app_db.py`

- [ ] Test deterministic macOS/Linux data, cache, and log path resolution with an injected base directory; forbid repository config from containing secrets.
- [ ] Test migration from an empty database, repeated migration idempotency, schema-version rejection, backup-before-upgrade, and symlink rejection.
- [ ] Run the two focused files; expect failures because modules do not exist.
- [ ] Implement `AppPaths` and `AppDatabase`; tables are `schema_version`, `repositories`, `jobs`, `job_events`, and `preferences` only.
- [ ] Run focused tests; expect PASS and no files outside the injected temporary directory.
- [ ] Commit: `feat: add local application state store`.

### Task 3: Create repository registry application service

**Files:**
- Create: `src/knowledge_compiler/application/dto.py`
- Create: `src/knowledge_compiler/application/repositories.py`
- Create: `tests/application/test_repository_service.py`

- [ ] Define tests for register/list/get/remove, duplicate canonical path, non-git path, unsafe symlink, missing path, dirty-state reporting, and removal that never deletes the repository.
- [ ] Run `pytest tests/application/test_repository_service.py -v`; expect import failure.
- [ ] Implement immutable DTOs carrying repository ID, display name, path, commit, branch, dirty flag, knowledge initialization state, and timestamps.
- [ ] Reuse `LocalGitRepositoryProvider`; do not reimplement git identity.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: add local repository registry service`.

### Task 4: Extract transport-neutral status and diagnostics services

**Files:**
- Create: `src/knowledge_compiler/application/status.py`
- Create: `src/knowledge_compiler/application/diagnostics.py`
- Modify: `src/knowledge_compiler/cli.py`
- Test: `tests/application/test_status_service.py`
- Test: `tests/application/test_diagnostics_service.py`
- Test: `tests/cli/test_view_commands.py`

- [ ] Write tests showing CLI status and application status serialize the same object/generation/run facts.
- [ ] Write credential, absolute-home-path, provider-output, and environment redaction tests for a diagnostics ZIP manifest.
- [ ] Run focused tests; expect failures before extraction.
- [ ] Implement services and refactor CLI to render their DTOs without changing current output/exit tests.
- [ ] Run focused tests; expect PASS and byte-identical existing CLI snapshots.
- [ ] Commit: `refactor: share status and diagnostics services`.

### Task 5: Add loopback API and stable error envelope

**Files:**
- Create: `src/knowledge_compiler/app/main.py`
- Create: `src/knowledge_compiler/app/server.py`
- Create: `src/knowledge_compiler/app/errors.py`
- Create: `src/knowledge_compiler/app/routes/system.py`
- Create: `src/knowledge_compiler/app/routes/repositories.py`
- Test: `tests/app/test_system_api.py`
- Test: `tests/app/test_repository_api.py`
- Test: `tests/app/test_error_envelope.py`

- [ ] Test `/api/v1/health`, `/version`, `/capabilities`, `/repositories`, registration, duplicate registration, and redacted failures.
- [ ] Test that non-loopback binding is rejected and no permissive CORS origin is configured.
- [ ] Run focused API tests; expect import/404 failures.
- [ ] Implement an app factory with injected paths/services and the approved `{error:{code,message,action,details}}` envelope.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: expose local system and repository API`.

### Task 6: Add one-command lifecycle and browser launch

**Files:**
- Create: `src/knowledge_compiler/app/launcher.py`
- Modify: `src/knowledge_compiler/cli.py`
- Test: `tests/cli/test_app_command.py`
- Test: `tests/app/test_launcher.py`

- [ ] Test port selection, already-running detection, explicit no-browser mode, graceful SIGINT, stale PID cleanup, and child-free shutdown.
- [ ] Run focused tests; expect command missing.
- [ ] Implement `knowledge app [--port] [--no-browser] [--data-dir]`; bind only loopback and open the browser after health is ready.
- [ ] Run focused tests; expect PASS.
- [ ] Commit: `feat: launch CodeWiki local app`.

### Task 7: Build and package the onboarding Web shell

**Files:**
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/app/App.tsx`
- Create: `web/src/api/client.ts`
- Create: `web/src/features/onboarding/OnboardingPage.tsx`
- Create: `web/src/features/repositories/RepositoryListPage.tsx`
- Create: `web/src/styles/tokens.css`
- Create: `web/src/styles/global.css`
- Test: `web/src/features/onboarding/__tests__/OnboardingPage.test.tsx`
- Test: `web/e2e/onboarding.spec.ts`
- Modify: `src/knowledge_compiler/app/server.py`

- [ ] Write component tests for empty, loading, API-unavailable, invalid-path, dirty-repository, and registered states.
- [ ] Write a keyboard-only E2E flow: open app → add fixture repo → land on repository overview shell.
- [ ] Run `pnpm --dir web test`; expect failure before components exist.
- [ ] Implement accessible semantic forms, visible focus, reduced-motion behavior, and responsive layout using the approved design tokens.
- [ ] Build assets and serve them from FastAPI with SPA fallback; API paths must never fall through to HTML.
- [ ] Run unit, typecheck, build, and E2E commands; expect PASS.
- [ ] Commit: `feat: add local onboarding web experience`.

### Task 8: Fresh-install and milestone documentation gate

**Files:**
- Create: `scripts/smoke_local_app.py`
- Create: `tests/integration/test_local_app_install.py`
- Create: `docs/runbooks/2026-09-17-local-app-install.md`
- Create: `docs/materials/validation/m9/README.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `HANDOFF.md`

- [ ] Test wheel build/install in a temporary venv, `knowledge app --no-browser`, health response, packaged SPA, and clean shutdown.
- [ ] Run `python -m build && pytest tests/integration/test_local_app_install.py -v`; expect PASS.
- [ ] Run `VERIFY_FAST=1 bash scripts/verify.sh`, frontend checks, and `python scripts/check_links.py`; expect all green.
- [ ] Capture the empty/onboarding screenshots and exact outputs in the M9 validation record.
- [ ] Update README current state and check D-027 surfaces.
- [ ] Commit: `docs: close M9 local product foundation` and push `main`.

