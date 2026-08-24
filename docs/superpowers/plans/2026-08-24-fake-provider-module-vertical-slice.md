# Fake Provider Module Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove one evidence-backed `ModuleKnowledge` object can move deterministically from a fake repository survey and bounded Evidence Pack through structural validation and fake semantic verification into one transactionally published generation containing canonical YAML, a Markdown Card, and a Wiki page.

**Architecture:** Add the smallest product-shaped pipeline behind the approved project-owned contracts. A fixture-backed `FakeEvidenceProvider` supplies normalized CodeWiki-like facts; submitted extraction and verification JSON fixtures exercise the shared semantic request/result boundary without calling an LLM; deterministic validation verifies Claim/Evidence bindings and local source integrity. Pure compilers stage canonical YAML, Card, and Wiki bytes, then a journaled generation publisher swaps all outputs and writes a manifest commit marker last. This slice does not add production CodeWiki integration, model calls, orchestration leases, incremental updates, HTML, FTS, or MCP.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML, Typer, pytest

**Specs:**
- `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md`
- `docs/spikes/codewiki-public-surface.md`
- `tests/fixtures/codewiki/0.6/cli-observations.json`

---

## Scope and invariants

- Implement only the `Module` knowledge type.
- The coordinator is a test-only vertical-slice harness, not a competing `RunOrchestrator`; it must not implement queues, leases, idempotency, repair, worker transport, or production CodeWiki behavior.
- Treat fixture repository text as data, never as instructions.
- The fake provider returns project-owned DTOs; production code never reads CodeWiki fixture JSON directly.
- Every module responsibility, public interface, dependency, relation, and summary statement must reference an existing Claim.
- Every Claim must reference an Evidence item present in the target Evidence Pack.
- Evidence paths must be relative, remain under the repository root after resolution, and carry valid inclusive line ranges plus verified source and excerpt SHA-256 hashes. Path traversal and symlink escape are rejected.
- `verified` requires both deterministic structural validation and a separate fake semantic-verification result that marks every required Claim `supported` against exactly its cited redacted excerpt.
- The compiler renders only validated Claim-backed fields and never calls a model.
- Failed validation or publication leaves the previously committed generation wholly unchanged.
- Canonical sort rules make permuted but semantically equivalent submissions byte-identical.
- Draft extraction and canonical verified objects are distinct types; an unverified draft can never be serialized or published as canonical IR.
- `snapshot_id` is deterministically derived from repository identity, commit, dirty flag, and filtered working-tree hash and must match at every contract boundary.
- Semantic verification is bound to a canonical digest of the exact Claim statements plus cited Evidence IDs and model-visible `excerpt_hash` values; changing redaction output invalidates the result even when source Evidence IDs are unchanged.
- Draft extraction supplies confidence/basis and versioned provenance, including an explicit generation timestamp. Canonicalization never reads the wall clock or invents provenance.

## Planned file structure

```text
pyproject.toml
src/knowledge_compiler/
├── contracts/
│   ├── __init__.py
│   ├── repository.py            # RepositorySnapshot identity, PlanTarget, EvidenceBudget
│   ├── evidence.py              # Repository survey and bounded Evidence Pack DTOs
│   ├── knowledge.py             # Canonical shared models and ModuleKnowledge DTOs
│   └── semantic.py              # Fake extraction/verification request-result contracts
├── providers/
│   ├── __init__.py
│   ├── base.py                  # EvidenceProvider protocol
│   └── fake.py                  # Fixture-backed deterministic provider
├── validation/
│   ├── __init__.py
│   └── module.py                # Structural Claim/Evidence validation
├── storage/
│   ├── __init__.py
│   └── generation.py            # Journaled three-output generation publication
├── compiler/
│   ├── __init__.py
│   ├── markdown.py              # Module Card and Wiki compilation
│   └── yaml.py                  # Canonical YAML compilation
└── vertical_slice.py            # Test-only vertical-slice harness and CLI
tests/
├── fixtures/fake_provider/
│   ├── survey.json
│   ├── evidence-pack.json
│   ├── module-extraction.json
│   └── module-verification.json
├── contracts/test_evidence_models.py
├── contracts/test_module_models.py
├── providers/test_fake_provider.py
├── validation/test_module_validation.py
├── storage/test_generation_publication.py
├── compiler/test_module_outputs.py
└── integration/test_module_vertical_slice.py
```

### Task 1: Define repository and bounded Evidence contracts

**Files:**
- Create: `src/knowledge_compiler/contracts/__init__.py`
- Create: `src/knowledge_compiler/contracts/repository.py`
- Create: `src/knowledge_compiler/contracts/evidence.py`
- Create: `tests/contracts/test_evidence_models.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `pyyaml>=6.0` to project dependencies and refresh `uv.lock`.**

- [ ] **Step 2: Write failing repository-contract tests.** Cover `RepositorySnapshot(repository_id, snapshot_id, root, branch, commit, dirty, working_tree_hash, eligible_files)`, `PlanTarget(id, type="module", topic, evidence_seeds)`, and `EvidenceBudget(max_items, max_characters, max_tokens)`. Define `snapshot_id` as `sha256:` plus the SHA-256 of canonical UTF-8 JSON `[repository_id, commit, dirty, working_tree_hash-or-empty]` using `ensure_ascii=False` and separators `(',', ':')`; reject a supplied mismatch. Also reject a relative repository root, nonpositive limits, and a target type other than `module` in this slice.

- [ ] **Step 3: Write a failing Evidence model test.** Construct an `EvidenceItem` with `id`, `provider`, `kind="source"`, relative `path`, `symbol`, positive `start_line/end_line`, `commit`, `content_hash="sha256:<64 hex>"`, `excerpt_hash`, redacted excerpt, `relationship`, and `strength="direct"`; assert it round-trips. Define `build_evidence_id` as `sha256:` plus the SHA-256 of canonical UTF-8 JSON `[repository_id, snapshot_id, normalized_posix_path, symbol-or-empty, start_line, end_line, content_hash]`. Add failures for absolute/traversing paths, `end_line < start_line`, malformed hashes, and a well-formed Evidence ID that does not equal the recomputed ID.

- [ ] **Step 4: Run the tests and verify RED.**

Run: `uv run --extra dev pytest tests/contracts/test_evidence_models.py -v`

Expected: import failure because `contracts.evidence` does not exist.

- [ ] **Step 5: Implement the approved DTO boundary.** Define the identity/ID constructors plus `RepositorySurvey(repository_id, snapshot_id, files, languages, symbols, graph_communities, configuration_facts)`, `GraphFact(source, predicate, target, confidence, provenance)`, `EvidenceItem`, and `EvidencePack(contract_version="0.1", repository, target, budget, evidence, graph_facts)`. Reject snapshot or Evidence ID mismatch, duplicate Evidence IDs, and item/character/token budget overflow. Use a deterministic injectable token counter in tests; do not add model-specific tokenization.

- [ ] **Step 6: Run the focused test and full suite.**

Run: `uv run --extra dev pytest tests/contracts/test_evidence_models.py -v && uv run --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit.**

```bash
git add pyproject.toml uv.lock src/knowledge_compiler/contracts tests/contracts
git commit -m "feat: define normalized evidence contracts"
```

### Task 2: Define canonical shared models and Claim-backed ModuleKnowledge

**Files:**
- Create: `src/knowledge_compiler/contracts/knowledge.py`
- Create: `tests/contracts/test_module_models.py`

- [ ] **Step 1: Write failing tests** for a valid `DraftModuleKnowledge` whose Draft Claims already contain extraction `Confidence(score, basis)` and whose extraction result carries versioned provenance with explicit `generated_at`; also test a stricter canonical `ModuleKnowledge` with supported verification. Cover duplicate Claim IDs, duplicate public-interface/dependency names, invalid stable IDs, factual fields with empty `claim_ids`, unsupported canonical Claim verification, and a summary or relation referencing an unknown Claim.
- [ ] **Step 2: Run RED:** `uv run --extra dev pytest tests/contracts/test_module_models.py -v`.
- [ ] **Step 3: Implement** shared payload models plus distinct `DraftClaim`/`DraftModuleKnowledge` and canonical `Claim`/`ModuleKnowledge`. Draft Claims contain extraction confidence/basis; the versioned `ExtractionResult` supplies full `Provenance(execution_mode, model, prompt_version, schema_version, generated_at)`. The draft has no `Validity` and cannot be passed to compilers or publisher. Canonical models add `ClaimVerification(status, verifier, evidence_ids, excerpt_hashes, verification_request_digest)`, full `Scope(repository, root, branch, commit, dirty, working_tree_hash)`, and `Validity`. Canonicalization copies—not regenerates—draft confidence and extraction provenance. Fix schema/type, require IDs matching `module.<domain>.<name>`, and permit canonical `validity.status="verified"` only when every required Claim has a `supported` verification result.
- [ ] **Step 4: Define canonical ordering** by Claim ID, interface name, dependency target, relation `(predicate, target)`, and Evidence ID. Add a permutation-invariance test proving two equivalent inputs serialize to the same normalized model dump.
- [ ] **Step 5: Run focused and full tests; expect PASS.**
- [ ] **Step 6: Commit:** `git commit -m "feat: define claim-backed module knowledge"`.

### Task 3: Add deterministic FakeEvidenceProvider fixtures

**Files:**
- Create: `src/knowledge_compiler/providers/__init__.py`
- Create: `src/knowledge_compiler/providers/base.py`
- Create: `src/knowledge_compiler/providers/fake.py`
- Create: `tests/fixtures/fake_provider/survey.json`
- Create: `tests/fixtures/fake_provider/evidence-pack.json`
- Create: `tests/providers/test_fake_provider.py`

- [ ] **Step 1: Write a failing contract test** that calls all four approved protocol methods with a `RepositorySnapshot`, `PlanTarget`, and `EvidenceBudget`: `inspect`, `ensure_index`, `build_pack`, and `get_evidence`. Assert the module pack contains only allowed repository-relative ranges for `CheckoutService` and `Inventory.reserve`.
- [ ] **Step 2: Run RED.**
- [ ] **Step 3: Define `EvidenceProvider`** with the exact approved methods: `inspect(repo)`, `ensure_index(repo)`, `build_pack(repo, target, budget)`, and `get_evidence(repo, evidence_id)`.
- [ ] **Step 4: Implement `FakeEvidenceProvider`** as a strict normalized JSON fixture loader bound to a supplied fixture repository root. `ensure_index` returns a deterministic no-op compatible status. Reject repository/snapshot/target mismatch and unknown Evidence IDs. It must not read CodeWiki fixtures or production source dynamically.
- [ ] **Step 5: Add fixture JSON** derived from the sanitized 0.6.5 contract shapes but normalized to project DTOs. Use deterministic IDs, graph facts, budgets, relationship/provider fields, and redacted excerpts from `tests/fixtures/probe_repo`; do not include absolute paths.
- [ ] **Step 6: Run focused and full tests; expect PASS.**
- [ ] **Step 7: Commit:** `git commit -m "test: add fake evidence provider contract"`.

### Task 4: Validate source integrity, Claim bindings, and fake semantic verification

**Files:**
- Create: `src/knowledge_compiler/validation/__init__.py`
- Create: `src/knowledge_compiler/validation/module.py`
- Create: `src/knowledge_compiler/contracts/semantic.py`
- Create: `tests/fixtures/fake_provider/module-extraction.json`
- Create: `tests/fixtures/fake_provider/module-verification.json`
- Create: `tests/validation/test_module_validation.py`

- [ ] **Step 1: Write failing source-integrity tests** proving validation rejects absolute/traversing paths, a symlink resolving outside the fixture root, a missing file, invalid UTF-8 source, an invalid inclusive line range, source `content_hash` mismatch, model-visible `excerpt_hash` mismatch, and a well-formed but incorrectly derived Evidence ID.
- [ ] **Step 2: Write failing binding tests** proving rejection of an unknown Evidence ID, unknown Claim ID in a summary/responsibility/interface/dependency/relation, missing required responsibility, snapshot mismatch, and a Claim with no evidence.
- [ ] **Step 3: Write failing semantic-contract tests.** Define versioned `ExtractionRequest/Result` and `VerificationRequest/Result` with `contract_version`, `run_id`, `target_id`, `operation`, `attempt`, `snapshot_id`, and `idempotency_key`. The extraction result contains `DraftModuleKnowledge`, draft confidence, and explicit provenance timestamp; only `apply_verification_result` may construct canonical `ModuleKnowledge`. Build `verification_request_digest` as SHA-256 of canonical UTF-8 JSON sorted by Claim ID, where each entry contains the exact Claim statement and sorted `(evidence_id, excerpt_hash)` pairs sent to verification. Prove verification fails for a cross-run result, stale/wrong attempt, wrong target/snapshot/operation/idempotency key, missing Claim, any `partial`/`unsupported`/`conflicted` Claim, differing Evidence IDs, differing excerpt hashes/redacted text, or a mismatched request digest.
- [ ] **Step 4: Run RED.**
- [ ] **Step 5: Implement `ValidationIssue` and `ModuleValidationResult`.** Return all issues in stable `(code, location)` order; never repair input.
- [ ] **Step 6: Implement exact local Evidence integrity validation.** Read the original file as bytes; reject invalid UTF-8; split the original bytes with `splitlines(keepends=True)`; join the 1-based inclusive range without changing CRLF/LF or trailing-newline bytes; compute `content_hash` over those exact joined bytes. Compute `excerpt_hash` independently over the exact redacted model-visible excerpt encoded as UTF-8. Resolve paths under the supplied repository root, reject symlink escape, recompute the canonical Evidence ID from that source hash, and compare commit/snapshot identity. No newline normalization is allowed.
- [ ] **Step 7: Implement structural and fake semantic validation.** Structural validation checks identity, uniqueness, membership, factual Claim references, and required payload fields on `DraftModuleKnowledge`. Build the `VerificationRequest` only from Claim-backed fields and the exact cited redacted excerpts, compute its canonical digest, and require `VerificationResult` plus every Claim verification to echo it. `apply_verification_result` correlates every request/result field (`contract_version`, `run_id`, `target_id`, `snapshot_id`, `attempt`, expected operation, operation-specific idempotency key, and request digest), binds the exact draft Claims/Evidence IDs/excerpt hashes, and constructs a new canonical `ModuleKnowledge` only when all required Claims are `supported`. It copies confidence and provenance from the validated extraction result and never calls the wall clock.
- [ ] **Step 8: Add valid extraction and verification fixtures** for `module.shop.checkout`, including summary, responsibilities, interfaces, dependencies, relation, confidence basis, and direct Evidence.
- [ ] **Step 9: Run focused and full tests; expect PASS.**
- [ ] **Step 10: Commit:** `git commit -m "feat: validate module evidence and semantic support"`.

### Task 5: Compile deterministic canonical YAML, Card, and Wiki bytes

**Files:**
- Create: `src/knowledge_compiler/compiler/__init__.py`
- Create: `src/knowledge_compiler/compiler/markdown.py`
- Create: `src/knowledge_compiler/compiler/yaml.py`
- Create: `tests/compiler/test_module_outputs.py`
- Create: `tests/golden/module-card.md`
- Create: `tests/golden/module-wiki.md`

- [ ] **Step 1: Write failing golden tests** for `compile_module_yaml`, `compile_module_card`, and `compile_module_wiki`. Assert dependencies and relations render with Claim/Evidence pointers, source citations use path/line ranges, and no unsupported prose appears.
- [ ] **Step 2: Add permutation and repetition tests** proving canonical ordering and byte-identical output for equivalent reordered input and repeated runs.
- [ ] **Step 3: Run RED.**
- [ ] **Step 4: Implement pure compiler functions.** Normalize the model with the Task 2 sort rules before `yaml.safe_dump(sort_keys=False, allow_unicode=True)`. Markdown compilers accept only the verified canonical object plus its validated pack; they perform no file access and call no model.
- [ ] **Step 5: Run focused and full tests; expect PASS.**
- [ ] **Step 6: Commit:** `git commit -m "feat: compile deterministic module outputs"`.

### Task 6: Publish one recoverable generation transaction

**Files:**
- Create: `src/knowledge_compiler/storage/__init__.py`
- Create: `src/knowledge_compiler/storage/generation.py`
- Create: `tests/storage/test_generation_publication.py`

- [ ] **Step 1: Write failing success tests** asserting one call stages and publishes canonical YAML, Card, Wiki, and `manifest.yaml` with matching `active_generation`, `agent_views_generation`, and `wiki_generation`; manifest is replaced last.
- [ ] **Step 2: Write parameterized failure-injection tests** for serialization/compiler failure and every staging flush/fsync/replace boundary. Seed generation N first, attempt generation N+1, simulate each failure, run startup recovery, and assert every visible file plus manifest remains byte-identical to N.
- [ ] **Step 3: Run RED.**
- [ ] **Step 4: Implement `GenerationPublisher`.** Precompile all bytes, stage under `.knowledge/state/transactions/<generation>/`, fsync staged files/directories, journal intended destinations and backups, replace canonical/Card/Wiki, then replace manifest as commit marker. On startup, restore backups for a journal without a matching committed manifest and remove completed journals.
- [ ] **Step 5: Run focused and full tests; expect PASS.**
- [ ] **Step 6: Commit:** `git commit -m "feat: publish recoverable module generation"`.

### Task 7: Wire the end-to-end vertical slice

**Files:**
- Create: `src/knowledge_compiler/vertical_slice.py`
- Create: `tests/integration/test_module_vertical_slice.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write a failing integration test.** Execute `run_fake_module_slice(provider, extraction_path, verification_path, output_root)` and assert a single committed generation contains canonical YAML plus Card/Wiki matching golden files and matching manifest generations.
- [ ] **Step 2: Add failure-path tests** for malformed fixture/extraction/verification JSON, hash mismatch, structural failure, semantic failure, compiler failure, and publication replacement failure. Assert a first run creates no visible generation and an update preserves the complete previous generation.
- [ ] **Step 3: Run RED.**
- [ ] **Step 4: Implement the test-only harness** in this order: resolve snapshot → ensure fake index → inspect → build bounded pack → verify local Evidence integrity → parse submitted extraction → structural validation → parse/apply separate fake semantic verification → precompile outputs → publish one generation transaction. Return a typed result with generation, object ID, and output paths. Do not add queues, leases, retries, repair, idempotency storage, or worker transport.
- [ ] **Step 5: Add script `knowledge-fake-module-slice`** with required `--repository-root`, `--fixtures`, `--extraction`, `--verification`, and `--output-root` options. It exits `0` on publication and `1` on validation/infrastructure failure.
- [ ] **Step 6: Run the integration test and CLI against a temporary output directory; expect PASS/exit 0.**
- [ ] **Step 7: Run the full suite and boundary scan.**

```bash
uv run --extra dev pytest -v
rg -n "from (backend|codewiki)\\.|import (backend|codewiki)|sqlite3|aiosqlite|SELECT .*code_(node|edge|chunk)" src tests
git diff --check
```

Expected: all tests pass, boundary scan has no matches, diff check is clean.

- [ ] **Step 8: Commit:** `git commit -m "feat: prove fake provider module vertical slice"`.

## Completion checks

- [ ] A single Module object completes the fake evidence-to-extraction-to-separate-verification-to-transactional YAML/Card/Wiki loop.
- [ ] Every factual field is Claim-backed and every Claim Evidence ID belongs to its bounded pack.
- [ ] Responsibilities, interfaces, dependencies, relations, and summary are all Claim-backed.
- [ ] Item, character, and token budgets are enforced before semantic fixtures are consumed.
- [ ] Local inclusive source ranges, source hashes, excerpt hashes, traversal, and symlink boundaries are verified.
- [ ] Invalid input or failure injection publishes no partial generation and preserves any prior generation.
- [ ] All output is canonicalized, permutation-invariant, deterministic, and golden-tested.
- [ ] Verification is bound to exact model-visible excerpt hashes/request digest, and canonical provenance comes only from explicit deterministic input.
- [ ] No CodeWiki implementation import, database query, LLM call, MCP server, FTS, HTML, incremental logic, or additional knowledge type is introduced.
- [ ] `pytest`, boundary scan, `git diff --check`, and `git status --short` show only intended changes.
