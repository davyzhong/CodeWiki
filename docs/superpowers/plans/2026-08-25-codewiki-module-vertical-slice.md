# CodeWiki Real-Provider Module Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove one real local Git repository produces the same verified `ModuleKnowledge` contract as M1 through public CodeWiki interfaces and a built-in LiteLLM semantic worker, without a persisted RunOrchestrator.

**Architecture:** Extend the M1 pipeline behind its existing contracts. A minimal `LocalGitRepositoryProvider` resolves a filtered repository snapshot; a `CodeWikiEvidenceProvider` adapts the captured public CLI surface into the project-owned Evidence DTOs; a one-Module planner turns deterministic survey facts into typed targets without Claims; a `LiteLLMWorker` implements `plan`/`extract`/`verify` over the same versioned semantic contracts the fake slice used; a non-orchestrated harness wires preflight through publication using the M1 validation, compilation, and storage layers unchanged.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML, Typer, pytest, CodeWiki 0.6 public CLI, LiteLLM (bounded version), `subprocess` argument-array invocation only

**Specs:**
- `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md`
- `docs/spikes/codewiki-public-surface.md`
- `tests/fixtures/codewiki/0.6/cli-observations.json`
- `docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md` (M1 contracts)

---

## Scope and invariants

- Every adapter field must be derived from the captured public-surface observations; undocumented JSON fields are never assumed.
- Invoke CodeWiki only through documented public CLI commands with argument arrays; never shell-interpolate repository text; never import `codewiki`/`backend` internals; never query its database. The single exception is the captured `package_version` probe (the spike's `python -c "from importlib.metadata import version; ..."` observation against the environment providing the `codewiki` executable), because `codewiki --version` exits 2 with no machine-readable output.
- The adapter normalizes public responses into project-owned Pydantic DTOs; raw provider output never enters canonical IR.
- Source bytes are read locally only after validating a provider-returned relative source reference under the resolved repository root; project-owned Evidence IDs and hashes are always recomputed.
- Preflight stops unsupported prerequisites (bad Git state, no commit, no eligible source, incompatible CodeWiki, missing model configuration) before any model call.
- Model names, endpoints, and credentials come from environment/user-level configuration and never enter the repository or run reports.
- The LiteLLM worker receives only target-bounded, redacted Evidence Pack content; credential-pattern detection and redaction run in `build_pack` when model-visible excerpts are produced from local source reads, `excerpt_hash` covers the redacted bytes, and the original `content_hash` is still compared locally; malformed output gets at most two worker-local repair attempts; evidence shortage returns `insufficient_evidence`.
- The planner may select targets and evidence seeds but can never emit Claims, prose, verification, or canonical objects.
- Live CodeWiki and live LLM tests are opt-in; deterministic CI runs on captured fixtures and a fake transport.
- No RunOrchestrator queues/leases/retries (M4), no ChangeSet/update behavior (M5), no five-type expansion (M3), no human overlay layer (M6), no MCP/FTS/HTML (M7).
- Repository text remains untrusted data everywhere.

## Planned file structure

```text
src/knowledge_compiler/
├── repository/
│   ├── __init__.py
│   └── local_git.py           # LocalGitRepositoryProvider + eligible-file inventory
├── providers/
│   ├── codewiki_cli.py        # subprocess runner: timeouts, size bounds, sanitized errors
│   └── codewiki.py            # CodeWikiEvidenceProvider over public commands
├── contracts/
│   └── planning.py            # PlanRequest, PlanTarget re-use, KnowledgePlan
├── planning/
│   ├── __init__.py
│   └── module.py              # deterministic one-Module planner over survey facts
├── workers/
│   ├── __init__.py
│   ├── base.py                # SemanticWorker protocol (plan/extract/verify)
│   ├── prompts.py             # extraction and verification prompt builders
│   └── litellm_worker.py      # LiteLLM-backed worker with injectable transport
├── config.py                  # .knowledge/config.yaml contract + secret rejection
├── preflight.py               # ordered preflight checks
├── cli.py                     # knowledge init + knowledge-fake/realslice commands home
└── real_slice.py              # non-orchestrated integration harness (M2 only)
tests/
├── repository/test_local_git.py
├── providers/test_codewiki_contract.py
├── planning/test_module_plan.py
├── workers/test_litellm_worker.py
├── test_config.py
├── cli/test_init.py
├── integration/test_real_provider_slice.py
└── fixtures/codewiki/0.6/     # normalized golden adapter fixtures (from observations)
```

### Task 1 (M2.1): This plan

- [ ] Independent plan review against the V0.1 design and captured surface; fix until approved; commit.

### Task 2 (M2.2): LocalGitRepositoryProvider and eligible-file inventory

**Files:** `src/knowledge_compiler/repository/`, `tests/repository/test_local_git.py`.

- [ ] **Step 1: Failing tests** for: normal repo snapshot; monorepo under one Git root; detached HEAD (branch `null`); shallow clone; dirty tree with per-file hashes and filtered working-tree hash; no remote (stable ID); no commit (stop); empty/no eligible source (stop); ignored files, binaries, dependency dirs, credential files, oversize files excluded; symlink escaping root excluded; `.knowledge/` and `.codewiki/` excluded even when tracked; unsupported-language files excluded from semantic evidence with a coverage report, failing when no supported code remains.
- [ ] **Step 2: Implement** `LocalGitRepositoryProvider.resolve(path) -> RepositorySnapshot`: stable repository ID derived from normalized identity — remote URL when present, else a content-derived `local:<initial-commit>` identity that stays stable when the repository moves or is renamed (never any path component) — with a test proving move-stability without a remote; branch/commit/detached/dirty metadata via Git plumbing commands with argument arrays, eligible-file inventory with relative path, blob ID when available, content hash, size, and language classification. Never store source content. `diff` raises `NotImplementedError` until M5.
- [ ] **Step 3: Compute the filtered working-tree hash** only from eligible files; prove generated knowledge never dirties the snapshot.
- [ ] **Step 4:** Focused/full tests, reviews, commit `feat: resolve local git repository snapshots`.

### Task 3 (M2.3): CodeWiki CLI runner and public adapter

**Files:** `src/knowledge_compiler/providers/codewiki_cli.py`, `providers/codewiki.py`, `tests/providers/test_codewiki_contract.py`, fixture normalization.

- [ ] **Step 1: Normalize the captured observations** into golden adapter fixtures: `repos_add`, `analyze`, `repos_scan`, `graph_search`, `graph_explore`, `graph_affected`, `update`, and `package_version` — absolute paths, timestamps, and machine IDs stripped; every field traceable to `cli-observations.json`. (`graph_search_after_update` is deliberately not normalized: its result shape is identical to `graph_search` and its incremental-update semantics belong to M5; the rationale is recorded here.)
- [ ] **Step 2: Write the shared EvidenceProvider contract suite once** (identity/budget/unknown-ID/paths) and run it against both the Fake provider and the fixture-backed CodeWiki adapter.
- [ ] **Step 3: Implement the CLI runner**: argument-array `subprocess`, supported-version gate `>=0.6,<0.7` (fail closed) implemented through the captured `package_version` probe resolved against the environment providing the `codewiki` executable — with fail-closed tests for missing, unparseable, and incompatible versions — plus timeouts, stdout/stderr size bounds, JSON parse limits, and sanitized diagnostics; never echo secrets.
- [ ] **Step 4: Implement `CodeWikiEvidenceProvider`**: `inspect` (repos scan + graph search/explore normalization), `ensure_index` (repos add + analyze full index only — the `update` and `graph_affected` commands are normalized into DTOs and fixture-tested as surfaces reserved for M5, never invoked by the M2 harness), `build_pack` (bounded graph explore + local source reads with recomputed hashes and project-owned Evidence IDs), `get_evidence`. Reject provider paths that escape the resolved root; enforce budgets before returning.
- [ ] **Step 4b: Implement credential redaction with a failing-first test**: `build_pack` runs credential-pattern detection over each locally read source range before constructing the model-visible excerpt; matched patterns are replaced with a `[REDACTED]` marker, `excerpt_hash` covers the redacted bytes, and the original-range `content_hash` is still computed and compared locally. Test with a planted API-key-like string in eligible source and assert the redacted excerpt differs, both hashes are consistent with their respective bytes, and the pack never contains the raw secret.
- [ ] **Step 5: Opt-in live tests** guarded by an environment marker; deterministic CI uses fixtures only.
- [ ] **Step 6:** Focused/full/boundary tests, reviews, commit `feat: adapt codewiki public interfaces`.

### Task 4 (M2.4): Preflight, configuration, and `knowledge init`

**Files:** `src/knowledge_compiler/config.py`, `preflight.py`, `cli.py`, `tests/test_config.py`, `tests/cli/test_init.py`.

- [ ] **Step 1: Failing config tests**: round-trip of the full field set (repository/evidence provider types, output language, semantic-worker extraction profile plus optional validation profile, exclusions, scope limits, default context budget), unknown keys, schema version, `zh|en` language, secret-field rejection (model endpoints, API keys, tokens), unsafe-path exclusions, copied-model corruption.
- [ ] **Step 2: Implement the config contract** and `knowledge init --language zh|en`: idempotent, never silently overwrites user configuration, generates `.gitignore` entries for `.knowledge/cache`, `.knowledge/state`, exports, and `.codewiki/` while preserving user content.
- [ ] **Step 3: Write failing preflight tests** enumerating each ordered stop — not a Git repository; no commit; no eligible source; `scope_limit_exceeded`; identity ambiguity; invalid config; unsupported/missing CodeWiki version; missing model profile — each proven to stop before any model call.
- [ ] **Step 3b: Implement ordered preflight**: Git validity → commit/eligible source/scope limits → repository identity → config/schema → CodeWiki version/readiness → model profile availability. Report the optional-validation-profile choice (reuse of the extraction profile with the separate verification prompt) in the preflight result per design §9.4.
- [ ] **Step 4:** Also move the `mcp` dependency from production to dev extras (M1 final-review carry-over) and refresh the lockfile.
- [ ] **Step 5:** Help/invalid-input/exit-code/sanitized-error tests; focused/full tests, reviews, commit `feat: add preflight configuration and init`.

### Task 5 (M2.5): One-Module Planner and KnowledgePlan contracts

**Files:** `src/knowledge_compiler/contracts/planning.py`, `planning/module.py`, `tests/planning/test_module_plan.py`.

- [ ] **Step 1: Failing tests** for versioned `PlanRequest`/`KnowledgePlan` identity (contract_version, run/repository/snapshot, operation, attempt, idempotency key), typed target priority and required-vs-optional flags (extending or wrapping the M1 `PlanTarget` so M4 run semantics need no breaking change), deterministic ordering for equivalent surveys, seed selection grounded in survey symbols/communities, `insufficient_evidence` without fabricated targets, and the planner-cannot-create-Claims boundary.
- [ ] **Step 2: Implement the deterministic one-Module planner**: derive module targets from graph communities and high-connectivity survey symbols; never emit Claims, prose, or verification.
- [ ] **Step 3:** Focused/full tests, reviews, commit `feat: plan one module from survey facts`.

### Task 6 (M2.6): Built-in LiteLLM SemanticWorker

**Files:** `src/knowledge_compiler/workers/`, `tests/workers/test_litellm_worker.py`.

- [ ] **Step 1: Add the LiteLLM dependency** with a bounded version; refresh the lockfile.
- [ ] **Step 2: Failing transport-injected tests** (no network): plan/extract/verify success; timeout; provider failure; malformed JSON; schema mismatch; two repair attempts then typed invalid; cross-run results rejected; secrets never appear in prompts or reports; extraction and verification prompts remain separate; evidence shortage → `insufficient_evidence`.
- [ ] **Step 3: Implement `LiteLLMWorker`** with an injectable transport so tests stay deterministic; structured JSON output required; redacted pack-only context; the M1 semantic request/result contracts reused verbatim.
- [ ] **Step 4: Opt-in live tests** skipped without credentials.
- [ ] **Step 5:** Focused/full/security tests, reviews, commit `feat: add litellm semantic worker`.

### Task 7 (M2.7): Real-provider integration harness and milestone gate

**Files:** `src/knowledge_compiler/real_slice.py`, `tests/integration/test_real_provider_slice.py`.

- [ ] **Step 1: Failing fixture-path integration test**: preflight → resolve → ensure index → survey → plan one Module → bounded pack → extraction → structural validation → separate verification → canonicalization → M1 publication, comparing contract-level results with the Fake path for the same normalized repository/Module scenario.
- [ ] **Step 2: Failure-path tests**: provider/model/validation/publication failures preserve the previous committed generation; no CodeWiki internals imported; planner output never contains Claims.
- [ ] **Step 3: Add the `knowledge-realslice` Typer command** with required `--repository-root`/`--output-root` options (model configuration from the environment), exit 0 published / 1 failure, sanitized diagnostics, help and invalid-input tests, and the `pyproject.toml` script entry, mirroring the M1 slice CLI.
- [ ] **Step 4: Opt-in live test** against a disposable committed fixture repository and a temporary output root.
- [ ] **Step 5:** Full suite, boundary scan, diff check, spec/quality reviews, milestone-wide review, push approved M2 to `origin/main`.

## Completion checks

- [ ] A real local Git repository produces one verified Module through public CodeWiki interfaces.
- [ ] Preflight stops unsupported/unsafe inputs before CodeWiki or LiteLLM work.
- [ ] The one-Module KnowledgePlan derives from deterministic survey facts and never contains Claims.
- [ ] Built-in plan/extract/verify share the M1 identity and evidence-bound contracts.
- [ ] The production adapter passes the same contract suite as the Fake provider.
- [ ] No CodeWiki internal import or database access exists.
- [ ] Credential patterns are redacted before any pack reaches the worker.
- [ ] LLM output cannot bypass structural or semantic validation.
- [ ] Provider/model failure preserves the previous committed generation.
- [ ] Deterministic CI runs without network or paid models.
