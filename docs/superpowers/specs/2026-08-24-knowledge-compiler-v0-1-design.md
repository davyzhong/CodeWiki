# Knowledge Compiler V0.1 Design

**Status:** Spec review approved; revised 2026-08-25 to add the human knowledge layer (user decision; multi-language remains deferred)
**Date:** 2026-08-24, revised 2026-08-25
**Product horizon:** Local repository first; Git URL support next; multi-repository workspaces later

## 1. Product definition

Knowledge Compiler is a local-first engineering knowledge compiler for coding agents. It reads one local Git repository, obtains deterministic code facts and bounded source evidence through CodeWiki, extracts evidence-backed knowledge into a canonical Knowledge IR, and compiles that IR into:

1. a Repo Wiki for human browsing;
2. typed Knowledge Cards for agent consumption;
3. task-specific context exposed through CLI and MCP.

The core product hypothesis is that precompiled, evidence-backed repository knowledge allows coding agents to complete repository tasks more accurately or with less exploratory work than using the repository alone.

## 2. Goals and non-goals

### 2.1 V0.1 goals

- Analyze one local Git repository, including a monorepo under one Git root.
- Use CodeWiki as the default code-evidence provider without forking it or reading its internal database.
- Generate five typed knowledge objects: Architecture, Module, Flow, Rule, and TechStack.
- Bind every factual field to source evidence through claim granularity.
- Support both Codex Skill and built-in LLM execution modes through one orchestrator.
- Validate objects structurally and semantically before publication.
- Accept protected human knowledge edits through an IR-level overlay layer; automated regeneration never silently overwrites or deletes human content.
- Persist canonical, version-aware Knowledge IR as reviewable YAML.
- Compile Markdown Repo Wiki pages, Markdown Knowledge Cards, and a standalone interactive HTML Wiki.
- Retrieve budgeted task context through CLI and seven MCP tools.
- Detect affected knowledge after source changes and selectively rebuild it.
- Provide a repeatable Agent A/B benchmark.

### 2.2 V0.1 non-goals

- Remote Git URL cloning, authentication, caching, or cleanup.
- Cross-repository knowledge or service topology.
- A long-running Web UI or SaaS service.
- Bidirectional merge of compiled Wiki/Card Markdown, human-content approval workflows, and team-oriented content governance. Human editing itself is in scope through the overlay layer (Section 6.5); the compiled output is never parsed back into IR.
- A custom AST parser, code graph, vector database, or repository watcher.
- Background generation, Git hooks, automatic commits, or code execution inside the target repository.
- Multiple synchronized output languages. One build uses either Chinese or English (confirmed by user decision 2026-08-25).
- A general enterprise knowledge platform or ingestion of tickets, chats, meetings, incidents, or external documents.

## 3. Stable product decisions

| Area | Decision |
|---|---|
| Primary input | One local Git repository |
| Future input | Git URLs through a RepositoryProvider extension |
| Evidence engine | CodeWiki through a versioned adapter |
| Canonical store | Independent Knowledge IR, not CodeWiki Wiki pages |
| Human view | Markdown Repo Wiki plus standalone interactive HTML |
| Agent view | Typed YAML/Markdown Knowledge Cards plus task context |
| Knowledge types | Architecture, Module, Flow, Rule, TechStack |
| Execution modes | Codex Skill and built-in LLM through one RunOrchestrator |
| Editing | Machine-verified content read-only; human overlay layer editable and protected (Section 6.5) |
| Primary success metric | Agent task effectiveness |
| Secondary success metric | Human-readable, source-grounded Wiki quality |

## 4. System boundary and architecture

```text
Local Git Repository
        |
        v
External CodeWiki
  scan / AST / graph / source chunks
        |
        v
CodeWikiEvidenceProvider (versioned JSON contract)
        |
        v
Repository Survey -> Knowledge Plan -> Bounded Evidence Packs
        |                                  |
        |                    +-------------+-------------+
        |                    |                           |
        |                    v                           v
        |              Codex Skill                Built-in LLM
        |                    |                           |
        |                    +-------------+-------------+
        |                                  |
        v                                  v
                     Draft Knowledge Objects
                                  |
                                  v
                   Structural + Semantic Validator
                                  |
                                  v
                      Canonical Knowledge IR
                         /          |          \
                        v           v           v
                  Repo Wiki   Knowledge Cards   Task Context
                 MD + HTML       YAML + MD       CLI + MCP
```

CodeWiki owns code facts. Knowledge Compiler owns knowledge semantics, claim-to-evidence binding, validity, storage, view compilation, and task selection.

CodeWiki's existing Wiki generator is a reference implementation and benchmark baseline. It is not the canonical source for V0.1 outputs because independently generated CodeWiki pages and Knowledge Cards could disagree. Both product views must be compiled from the same Knowledge IR.

## 5. Component boundaries

### 5.1 RepositoryProvider

Resolves an input into an immutable repository snapshot identity.

```python
class RepositoryProvider(Protocol):
    def resolve(self, path: Path) -> RepositorySnapshot: ...
    def diff(self, baseline: FileInventory, current: FileInventory) -> ChangeSet: ...
```

`RepositorySnapshot` contains the absolute root, stable repository ID, branch, commit, remote URL when present, dirty flag, eligible-file inventory, and working-tree hash when dirty. V0.1 implements only `LocalGitRepositoryProvider`.

The eligible-file inventory permanently excludes `.knowledge/`, `.codewiki/`, `.git/`, ignored files, dependency directories, binary files, and configured oversize files. The dirty flag and working-tree hash use this filtered inventory rather than raw `git status`, so generated knowledge and CodeWiki indexes never make their own source snapshot dirty. The same exclusion is passed to CodeWiki indexing.

### 5.2 EvidenceProvider

Provides code facts without exposing the provider's internal storage.

```python
class EvidenceProvider(Protocol):
    def inspect(self, repo: RepositorySnapshot) -> RepositorySurvey: ...
    def ensure_index(self, repo: RepositorySnapshot) -> IndexStatus: ...
    def build_pack(
        self,
        repo: RepositorySnapshot,
        target: PlanTarget,
        budget: EvidenceBudget,
    ) -> EvidencePack: ...
    def get_evidence(self, repo: RepositorySnapshot, evidence_id: str) -> EvidenceItem: ...
```

V0.1 implements `CodeWikiEvidenceProvider` through CodeWiki's machine-readable CLI surface. It does not import CodeWiki internals or query its SQLite/PostgreSQL tables. Repository change detection belongs to `RepositoryProvider`, is computed before CodeWiki sync, and remains available when the CodeWiki cache is missing.

The first implementation targets the CodeWiki 0.6 minor series. Before feature implementation, a blocking adapter spike must run these capabilities against a committed fixture repository and capture their JSON as contract fixtures:

| Provider need | CodeWiki 0.6 command family | Required result |
|---|---|---|
| Register repository | `codewiki repos add <path> --json` | Stable provider repository identifier |
| Full index | `codewiki analyze <repo> --json` | Successful run plus indexed snapshot metadata |
| Incremental index | `codewiki update <repo> --json` | Successful catch-up after Knowledge Compiler computes its own `ChangeSet` |
| Repository survey | `codewiki repos scan <repo> --json`, graph search, and indexed files | Files, languages, symbols, routes, graph communities, and configuration facts |
| Target exploration | `codewiki graph explore <topic> --json` and graph query/trace commands | Bounded nodes, edges, and source references |
| Affected symbols | `codewiki graph affected --stdin --json` | Provider hints for a supplied changed-file list |

The adapter normalizes captured provider JSON into project-owned Pydantic DTOs. Raw source snippets are read locally from the resolved repository only after CodeWiki returns an allowed source reference; they do not depend on a CodeWiki evidence ID. If any required command lacks usable machine-readable data, the spike tries the equivalent documented CodeWiki MCP/HTTP surface. If neither public surface satisfies the contract, implementation stops and reports the missing capability instead of importing internals. The design must then be revised before feature work continues.

Knowledge Compiler evidence IDs are content-addressed and provider-independent:

```text
sha256(repository_id, snapshot_id, path, symbol, start_line, end_line, source_content_hash)
```

They are stable for unchanged source within the same repository snapshot and are rebuilt when source content or range changes.

### 5.3 Planner

Consumes `RepositorySurvey` and produces a `KnowledgePlan`. It selects investigation targets and evidence seeds; it never creates final claims. Planning can use the selected semantic worker, but deterministic repository facts are always supplied first.

### 5.4 RunOrchestrator and semantic workers

```python
class SemanticWorker(Protocol):
    def plan(self, request: PlanRequest) -> KnowledgePlan: ...
    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...
    def verify(self, request: VerificationRequest) -> VerificationResult: ...
```

`RunOrchestrator` owns target queues, leases, idempotency, structural validation, semantic work scheduling, repair counters, publication, and final run status. Semantic workers only transform a versioned request into a versioned result.

Two execution modes use the same request and result schemas but different transport:

- Agent mode: Codex leases a target from the orchestrator, submits extraction or verification results with a lease token and idempotency key, and may resume an interrupted run.
- Built-in mode: `LiteLLMWorker` consumes the same queue in-process. One configured extraction profile and one optional validation profile produce structured JSON. V0.1 has no model-routing UI or complex routing policy.

Every semantic request/result contains `contract_version`, `run_id`, `target_id`, `operation`, `attempt`, `snapshot_id`, and `idempotency_key`. Duplicate submissions with the same idempotency key return the recorded result without repeating publication or model work.

### 5.5 Validator

Performs deterministic structural checks and semantic-worker-backed entailment checks. Only objects passing both stages become `verified`.

### 5.6 KnowledgeStore

Loads, validates, and transactionally writes canonical YAML objects, `plan.yaml`, and default Agent surfaces. Drafts are written to run staging first. A publish transaction backs up replaced files/directories, writes a journal, swaps canonical objects, the latest plan/target results, the verified-only Cards directory, and the generation-stamped FTS database, writes the manifest last as the commit marker, and then removes the journal. Startup restores backups for any journal without a commit marker. Failed updates preserve the previous object but mark it stale.

### 5.7 Compiler

Transforms active canonical IR into Wiki Markdown, Cards Markdown, deterministic Mermaid diagrams, and standalone HTML. Wiki compilation accepts verified and stale objects so humans can see expiry warnings. Agent Cards, FTS, and task context accept only verified objects. The compiler cannot call an LLM or introduce new claims.

### 5.8 ContextRetriever

Indexes verified objects in a local SQLite FTS5 cache, expands one hop through explicit Knowledge relations, ranks type-aware results, and compiles a context package under a token budget. Before every default Agent read, it requires the repository snapshot, `active_generation`, `agent_views_generation`, and FTS generation stamp to match; a mismatch fails closed with `knowledge_update_required`. It excludes stale objects by default. Invalid, conflicted, and insufficient-evidence target results are never canonical objects.

### 5.9 MCP server

Exposes read-only knowledge and evidence retrieval over stdio. It does not perform builds or mutate the target repository.

### 5.10 Human knowledge layer

Loads and validates Git-tracked human overlays under `.knowledge/human/`. An overlay carries human-authored supplements, field overrides, and notes with an explicit timestamp and optional evidence pointers. The layer is a read-only input to compilation, retrieval, and regeneration: no automated process rewrites, regenerates, or deletes overlay content. `knowledge edit <object-id>` is the supported edit surface.

## 6. Canonical Knowledge IR

### 6.1 Base object

```yaml
schema_version: "0.1"
id: flow.order.create
type: flow
title: Create Order Flow
summary:
  text: Creates an order after inventory reservation and payment initiation.
  claim_ids:
    - flow.order.create.claim.inventory-first
scope:
  repository: ecommerce
  branch: main
  commit: abc123
  dirty: false
claims:
  - id: flow.order.create.claim.inventory-first
    statement: Inventory is reserved before payment creation.
    evidence:
      - ev.order-service.create-order.01
    confidence: 0.96
relations:
  - predicate: involves
    target: module.inventory
    claim_ids:
      - flow.order.create.claim.inventory-first
validity:
  status: verified
  verified_commit: abc123
provenance:
  execution_mode: codex-skill
  model: null
  generated_at: 2026-08-24T00:00:00Z
```

Stable semantic IDs use `<type>.<domain>.<name>` rather than opaque database identifiers.

### 6.2 Shared models

- `Scope`: repository, branch, commit, root path, dirty flag, and working-tree hash.
- `Claim`: stable ID, statement, evidence IDs, confidence, and verification result.
- `EvidenceRef`: provider, kind, path, symbol, line range, commit, original source hash, redacted excerpt hash, relationship, and strength.
- `ClaimBackedText`: text plus the verified Claim IDs that support it.
- `Relation`: predicate, target object, and supporting Claim IDs.
- `Confidence`: normalized score and basis.
- `Provenance`: execution mode, semantic worker/model, prompt/schema versions, and generation time.
- `Validity`: status, verified commit, stale reason, and validation report.

### 6.3 Typed payloads

- `ArchitectureKnowledge`: components, boundaries, and relationships, each referencing supporting Claim IDs.
- `ModuleKnowledge`: responsibilities, public interfaces, and dependencies, each referencing supporting Claim IDs.
- `FlowKnowledge`: trigger, ordered steps, participants, and failure paths, each referencing supporting Claim IDs.
- `RuleKnowledge`: statement, severity, applicability, and exceptions, each referencing supporting Claim IDs.
- `TechStackKnowledge`: technologies, versions, categories, and configuration evidence, each referencing supporting Claim IDs.

A factual field is any statement about repository structure, behavior, dependency, constraint, technology, version, configuration, or flow. Every factual field must either reference one or more verified Claims or be a deterministic projection of Claim-backed fields. Titles, IDs, ordering labels, and presentation headings are non-factual metadata. Summaries use `ClaimBackedText`; they are not unverified prose.

Mermaid edges, Wiki statements, Card statements, and task-context statements are generated only from verified Claim-backed payload fields. The compiler cannot render an unsupported typed-payload fact.

### 6.4 Validity states

Published canonical objects have only two validity states:

```text
verified -> stale
```

Run targets, which are stored in the plan and run report rather than as canonical objects, have these terminal results:

- `verified`: a canonical object was published;
- `invalid`: schema, reference, or validation failure;
- `conflicted`: supplied evidence supports incompatible conclusions;
- `insufficient_evidence`: the worker declined to create an object;
- `retired`: a deterministic retirement check removed a previously published object;
- `skipped`: an optional target was deliberately omitted by policy.

For object aggregation, every required factual Claim must be `supported`. A `partial` or `unsupported` required Claim makes the draft invalid and eligible for repair. A `conflicted` Claim makes the target conflicted. Optional factual fields with partial or unsupported Claims must be removed during repair before publication; they cannot remain in a verified object.

Machine-generated canonical objects carry no human-verified or human-locked state; human knowledge lives exclusively in the overlay layer of Section 6.5.

### 6.5 Human overlays

Human knowledge is protected by storing it beside the canonical IR, not inside machine-verified objects:

```yaml
# .knowledge/human/modules/module.shop.checkout.yaml
schema_version: "0.1"
object_id: module.shop.checkout
updated_at: 2026-08-25T12:00:00+08:00
sections:
  - field: summary
    mode: supplement            # supplement | override
    text: Checkout holds a repository-wide lock during peak season.
    basis: postmortem 2026-07
notes:
  - id: module.shop.checkout.note.peak-load
    text: Reservation contention rises sharply during promotions.
    basis: operations experience
    evidence: []                # optional path/symbol/document pointers
```

Protection rules:

- `supplement` adds attributed human content to an object and is always preserved by regeneration.
- `override` replaces the rendered text of one factual field; the machine-verified Claim remains recorded and is rendered as a collapsible original so verified knowledge is never hidden from review.
- Human entries carry `execution_mode: human` provenance and an explicit `updated_at` supplied by the edit tool; compilers never invent timestamps.
- When regeneration produces changed evidence for a machine field that carries a human override, the target result is `conflicted`: the previous generation and the overlay both remain until a human resolves the conflict. Neither direction wins silently.
- Overlays live under `.knowledge/` and are therefore outside the eligible-file snapshot; editing knowledge never dirties the repository scan.
- Overlay files are never automatically deleted. Retiring an object archives its overlay; an overlay without a live canonical object still renders in the Wiki under an orphaned-human-knowledge warning rather than disappearing.
- Human text is untrusted data: the same escaping and prompt-injection-as-data rules apply as for repository text.
- The edit surface is `knowledge edit <object-id>` plus direct editing of the Git-tracked overlay file. Compiled Markdown is never parsed back into IR.

## 7. Evidence Pack contract

Every extraction target receives a versioned, bounded pack:

```yaml
contract_version: "0.1"
repository:
  id: ecommerce
  root: /absolute/path
  branch: main
  commit: abc123
  dirty: false
target:
  id: flow.order.create
  type: flow
  topic: create order
evidence:
  - id: ev.order-service.create-order.01
    kind: source
    path: src/order/service.ts
    symbol: createOrder
    start_line: 118
    end_line: 164
    commit: abc123
    content_hash: sha256:...
    excerpt_hash: sha256:...
    excerpt: ...
    strength: direct
graph_facts:
  - source: OrderService.createOrder
    predicate: calls
    target: InventoryService.reserve
    confidence: deterministic
```

`content_hash` verifies the original local source range. Credential redaction produces the model-visible excerpt and `excerpt_hash`; semantic verification uses exactly that redacted excerpt. Structural validation compares the original source hash locally without returning secret text to a model.

The pack has explicit item, character, and token budgets. A worker may request a bounded expansion using named seeds, but it cannot silently ingest an unlimited GraphRAG context. When available evidence cannot support the requested knowledge, the worker returns `insufficient_evidence` instead of guessing from names, comments, or conventions.

## 8. Storage layout

```text
.knowledge/
├── config.yaml
├── manifest.yaml
├── plan.yaml
├── baseline/
│   └── eligible-files.json
├── objects/
│   ├── architecture/
│   ├── modules/
│   ├── flows/
│   ├── rules/
│   └── tech-stack/
├── views/
│   ├── wiki/
│   └── cards/
├── exports/
│   └── repo-wiki.html
├── cache/
│   ├── evidence/
│   └── knowledge-index.sqlite3
└── state/
    └── runs/<run-id>/
```

Tracked by default:

- `config.yaml` without secrets;
- `manifest.yaml` and `plan.yaml`;
- `baseline/eligible-files.json` so incremental comparison survives cache deletion and machine changes;
- canonical `objects/**/*.yaml`;
- compiled `views/wiki/**/*.md` and `views/cards/**/*.md`.

Ignored by default:

- `cache/` and `state/`;
- `exports/repo-wiki.html` because it is reproducible;
- the CodeWiki local index.

Users may explicitly commit the standalone HTML export.

The generated target-repository ignore rules always exclude `.knowledge/` and `.codewiki/` from evidence scanning and snapshot hashes even though selected `.knowledge/` files are tracked by Git. This exclusion is enforced in `RepositoryProvider` and the CodeWiki adapter, not delegated only to `.gitignore`.

`manifest.yaml` separates:

- `observed_snapshot`: the most recent eligible-file inventory examined by a run;
- `active_generation`: the canonical object generation committed by a publish transaction;
- `agent_views_generation`: the verified-only Cards and FTS generation committed in the same transaction as `active_generation`;
- `wiki_generation`: the generation for which human Wiki/HTML views were successfully compiled;
- `pending_targets`: stale or failed required targets that must run again even when no new file diff exists.

The tracked eligible-file inventory contains path, Git blob ID when available, content hash, size, and language classification. It never stores source content.

`plan.yaml` persists the latest target set, required/optional priority, last terminal result, published object ID when any, and retry/pending status. Run reports add detailed attempts and diagnostics, but deleting ignored run reports does not remove the state required by `knowledge status` or the next update.

## 9. Planning, extraction, validation, and publication

### 9.1 Preflight

Before model use, the tool verifies the Git repository, repository identity, supported CodeWiki version, CodeWiki index, schema compatibility, and execution-mode configuration. Unsupported or unavailable prerequisites stop before any LLM call.

### 9.2 Planning

The survey includes directory structure, languages, entry points, high-connectivity modules, public routes and interfaces, configuration files, graph communities, and test structure. The planner produces typed targets with priorities and evidence seeds. It cannot create final claims.

### 9.3 Agent flow

The user invokes `/knowledge-build` or `/knowledge-update`. `RunOrchestrator` persists this target state machine:

```text
queued
  -> evidence_ready
  -> extraction_leased
  -> draft_submitted
  -> structural_validated
  -> semantic_pending
  -> verification_leased
  -> verified
```

Repairable failures move to `repair_pending` and then back to `extraction_leased`; terminal results are `invalid`, `conflicted`, `insufficient_evidence`, `retired`, or `skipped`. A lease contains a run ID, target ID, operation, expiry, attempt, and idempotency key. Expired leases return to their prior queue without losing submitted results.

The Skill uses:

```text
knowledge prepare
knowledge next --operation extraction
knowledge evidence <target>
knowledge submit-extraction <draft.json> --lease <token>
knowledge verify-next
knowledge submit-verification <result.json> --lease <token>
knowledge finalize
```

The orchestrator, not the Skill, increments repair attempts, schedules semantic verification, decides publication eligibility, and computes the final run status. Agent semantic verification uses a fresh verification request containing only Claim-backed fields and their cited redacted evidence; it does not reuse extraction conversation context.

### 9.4 Built-in LLM flow

```bash
knowledge build --executor llm
knowledge update --executor llm
```

The built-in worker consumes the same persisted queue and receives the same plan target, Evidence Pack, JSON Schema, budgets, operation-specific request, and anti-hallucination rules as the Skill path. If no validation profile is configured, it reuses the extraction model profile with the separate verification prompt and request contract; preflight reports this choice.

### 9.5 Structural validation

Mandatory checks include:

- Pydantic and JSON Schema validity;
- stable ID and type correctness;
- referenced Evidence IDs exist in the input pack;
- paths, line ranges, symbols, commits, and content hashes are valid;
- every factual field is Claim-backed or deterministically derived from Claim-backed fields;
- every required Claim has evidence;
- relation targets exist or are explicitly unresolved;
- typed references such as Flow steps and Rule applicability are valid;
- compiler-required fields are present.

### 9.6 Semantic validation

A separate verification phase classifies each Claim-backed fact as `supported`, `partial`, `unsupported`, or `conflicted` using only the fact and its cited redacted evidence. Only fully supported required facts can enter a verified object. Extraction and verification use separate requests, prompts, idempotency keys, and contracts even when they use the same configured model.

### 9.7 Repair and publication

Each target receives at most two repair attempts after its initial submission. Continued failure leaves a run-target result and does not publish a new object. Other verified objects may publish.

A run is `complete` when all required targets are verified or deterministically retired, no previously published object remains stale, and all requested views compiled. Optional targets may end as insufficient or skipped with warnings. A run is `partial` when any required target is neither verified nor retired, any previous object remains stale, or any requested view failed to compile. A run is `failed` when preflight fails or no usable canonical generation exists.

Regeneration never rewrites or deletes human overlays. When regenerated machine content changes the evidence under a machine field carrying a human `override`, the target ends `conflicted`, the previous generation and the overlay both remain, and the conflict is listed for human resolution.

Drafts live under `.knowledge/state/runs/<run-id>/drafts/`. Publication uses the transaction journal described in `KnowledgeStore`; canonical object files and `active_generation` commit together. A failed update preserves the previous content but marks it stale in the canonical object and adds its target to `pending_targets`.

Verified-only Markdown Cards and the FTS database are part of the same recoverable publish transaction as canonical objects. An invalidation transaction runs before semantic regeneration: affected objects become stale, staged Agent Cards omit them, staged FTS omits them, the directories/database swap under the transaction journal, and the manifest commits matching `active_generation` and `agent_views_generation`. A later successful extraction transaction replaces stale objects with verified ones and republishes matching Agent surfaces.

Human Wiki/HTML compilation occurs after that transaction because it may include stale diagnostic content. A Wiki compiler failure does not roll back valid IR or safe Agent surfaces; it leaves `wiki_generation` behind `active_generation`, returns `partial`, and allows `knowledge compile` to retry deterministically.

All default CLI/MCP Agent reads also compare the current filtered repository snapshot with the manifest snapshot and verify generation equality. If a publish transaction fails or source changes without a successful `knowledge update`, reads return `knowledge_update_required` rather than serving the previous Cards/FTS. Explicit stale-diagnostic reads are separate and visibly marked.

## 10. Compiled views

### 10.1 Repo Wiki

```text
views/wiki/
├── index.md
├── architecture.md
├── modules/*.md
├── flows/*.md
├── rules.md
├── tech-stack.md
└── sources.md
```

Deterministic templates organize claims, relations, object links, and Evidence references into readable pages. Mermaid diagrams are derived from Architecture relationships, Module dependencies, and Flow steps. The compiler never calls an LLM.

Wiki pages include both verified and stale canonical objects. Stale sections show the previous verified snapshot, stale reason, last verified commit/hash, and pending target; they are never rendered without an expiry banner. Human overlay content persists through regeneration and renders with explicit human attribution; a human `override` shows the machine-verified original as a collapsible alternative.

The standalone HTML contains catalog navigation, heading navigation, full-text search, rendered Mermaid diagrams, object links, collapsible evidence, freshness, commit, and generation metadata. Source links target a fixed remote commit when a remote URL exists; otherwise the page displays local path, symbol, line range, and excerpt.

`knowledge open` compares `wiki_generation` with `active_generation`. When the Wiki is behind, it displays a global stale-view warning before opening the existing HTML and directs the user to run `knowledge compile`; an old Wiki is never presented as current merely because individual stale banners were not compiled.

### 10.2 Knowledge Cards

Each verified canonical object YAML is the machine-readable source for a Knowledge Card; the compiler produces one dense Markdown rendering for convenient inspection. There is no second derived Card YAML. Published Agent Card views include only verified objects. When an object becomes stale, its Markdown Card and FTS row are removed in the invalidation transaction, while its canonical YAML remains available for diagnostics and Wiki warnings. Cards retain the ID, type, Claim-backed summary, key claims, relations, relevant constraints, evidence pointers, and version identity. They omit large source excerpts. Attributed human overlay notes render in Cards with `source: human` markers; human `override` text replaces the rendered field text while the machine-verified Claim stays recorded in the canonical object.

### 10.3 Task context

```bash
knowledge context "Add cash on delivery to the order flow" \
  --format markdown \
  --budget 6000
```

Selection uses SQLite FTS5 over verified objects, one-hop explicit relation expansion, type-aware ranking that favors applicable Rules and Flows, and token-budget compilation. Source bodies are fetched on demand rather than included by default. Stale objects are excluded unless explicitly requested for diagnosis; invalid, conflicted, and insufficient-evidence results are not canonical objects and therefore cannot enter retrieval. Human overlay entries participate in retrieval with `source: human` attribution.

`knowledge context <task> --include-stale` is a diagnostic-only mode. It bypasses default ranking, labels every stale object and stale reason, and never presents the result as safe coding context.

## 11. MCP interface

The stdio server exposes exactly seven V0.1 tools:

```text
knowledge_repo_overview
knowledge_search
knowledge_get_object
knowledge_get_related
knowledge_get_evidence
knowledge_context_for_task
knowledge_status
```

Tools return structured JSON and compact Markdown. The MCP server is read-only and never runs builds. Human overlay content is exposed through the object, related, context, and overview tools with `source: human` attribution and never silently merged into machine-verified fields.

`knowledge_get_object` and `knowledge_status` accept an explicit `include_stale` diagnostic flag. `knowledge_context_for_task` defaults to verified-only and accepts `include_stale=true` only as a visibly marked diagnostic response. All other calls fail closed on snapshot or generation mismatch.

## 12. Incremental update

```text
Load tracked eligible-file baseline
  -> Resolve current filtered RepositorySnapshot
  -> Compare inventories before CodeWiki sync
  -> CodeWiki full index or incremental update
  -> Provider affected-symbol hints
  -> Evidence reverse index
  -> affected Claims and Objects
  -> mark stale
  -> rebuild bounded Evidence Packs
  -> re-extract and validate
  -> recompile affected views and FTS records
```

The tracked `baseline/eligible-files.json` is authoritative for file-level change detection. Comparison handles committed changes, dirty-to-dirty runs, new untracked eligible files, deletion, and rename; a rename is normalized to delete plus add unless both Git and content hash prove identity. It does not require the previous CodeWiki cache or Git history, so it works after cache deletion, on shallow clones, and after switching commits.

Change detection always runs before CodeWiki sync so provider index mutation cannot erase the comparison baseline. CodeWiki then performs an incremental update when its compatible cache exists or a full index when the cache is absent/incompatible. Provider affected-symbol output enriches the already-computed file change set; it does not replace it.

If CodeWiki indexing fails during update, the tool still commits an invalidation transaction for every object whose Evidence paths intersect the file ChangeSet and every verified object one relation hop from those objects. Those targets enter `pending_targets`; no semantic regeneration runs, new targets are not claimed as discovered, and the command returns `partial`. If no prior canonical generation exists, indexing failure returns `failed`.

A full planner refresh occurs when the manifest, baseline, or schema is missing/corrupt; repository identity changes; the current repository has no usable eligible files; or CodeWiki must rebuild an incompatible index and cannot reproduce prior graph identities. The planner refreshes affected areas when entry points, module directories, routes, dependency/configuration topology, or graph communities change. Ordinary implementation changes only reprocess objects referencing affected files, symbols, or content hashes.

At run end, `observed_snapshot` and the eligible-file baseline advance to the current scan even for a partial run, while every unresolved required target is retained in `pending_targets`. Therefore a later update retries stale work even when no additional files changed. `active_generation` advances only through a successful canonical publish transaction.

### 12.1 Deterministic object retirement

Planner omission never deletes or retires an existing object. Source deletion first marks the object stale and creates a `retirement_pending` target. Retirement is allowed only when all of these checks pass:

1. every Evidence source for the object is absent from the current eligible-file inventory or its referenced symbol/range no longer exists;
2. a deterministic provider-wide exact-symbol, path, graph-node, and lexical FTS search using stored former anchors finds no current candidate evidence. Vector search, LLM summaries, and semantic-worker output are forbidden in this decision;
3. no verified object retains an inbound relation to the candidate. Inbound objects are refreshed first and must either verify without that relation or independently become retirement candidates;
4. every provider query completed successfully on the current snapshot. Unsupported languages, provider errors, truncated results, or inconclusive limits keep the object stale rather than authorizing deletion.

Passing all checks yields target result `retired`. The core publish transaction journals and atomically commits deletion of the object YAML, deletion of its Markdown Card, removal of its FTS row, the updated `plan.yaml`, and the manifest generation. Only the human Wiki section/page and Wiki object links are removed by subsequent Wiki compilation. If any check cannot complete, the object remains stale and pending; it is never silently deleted.

A semantic re-extraction may run before the deterministic check to discover replacement knowledge. A verified replacement cancels retirement, but `insufficient_evidence` or any other model result never authorizes deletion.

If regeneration fails, previous content remains visible as stale, default task context excludes it, the Wiki renders an expiry warning, and the command returns `partial`. V0.1 updates only on an explicit command or Skill action; there is no watcher or Git hook. Invalidation and retirement never modify human overlays: overlays survive stale marking and pending retries, retiring an object archives its overlay, and an overlay whose object is retired renders under the Wiki orphaned-human-knowledge warning until a human edits or removes it.

## 13. CLI and configuration

Primary commands:

```text
knowledge init --language zh|en
knowledge build --executor llm
knowledge update --executor llm
knowledge edit <object-id>
knowledge status
knowledge validate
knowledge compile
knowledge context <task> [--format json|markdown] [--budget N] [--include-stale]
knowledge open
knowledge serve
```

`knowledge edit <object-id>` creates or opens the object's Git-tracked overlay under `.knowledge/human/` in the user's editor (or prints the overlay path with `--print-path` for non-interactive flows), validates the saved overlay against the Section 6.5 contract, and reports typed issues without touching any other file. An invalid overlay never blocks reading existing generations but fails the next build or update with explicit overlay issues.

Agent-only queue commands are the stable internal Skill interface and may be hidden from the primary help group:

```text
knowledge prepare
knowledge next --operation extraction
knowledge evidence <target>
knowledge submit-extraction <draft.json> --lease <token>
knowledge verify-next
knowledge submit-verification <result.json> --lease <token>
knowledge finalize
```

`config.yaml` stores repository/evidence provider types, output language, semantic-worker profile names, and default context budget. Model names, endpoints, and API keys come from environment variables or user-level configuration and never enter the repository.

Exit codes:

- `0`: complete;
- `1`: failed with no usable result;
- `2`: partial with one or more unpublished or stale objects.

Every mutating run writes a structured report under `state/runs/<run-id>/`. Status reports two separate groups: published canonical objects (`verified`, `stale`) and current/latest plan-target results (`verified`, `invalid`, `conflicted`, `insufficient_evidence`, `retired`, `skipped`).

## 14. Security and privacy

- Never execute repository code, installation scripts, build scripts, or tests.
- Respect `.gitignore`, CodeWiki ignore rules, binary exclusions, size limits, dependency-directory exclusions, and common credential-file exclusions.
- Run credential-pattern detection and redaction before an Evidence Pack is sent to a model.
- Never persist API keys in logs, reports, prompts, or `.knowledge/`.
- Send only target-bounded evidence to a model.
- Escape Markdown, source excerpts, and diagram inputs when producing HTML.
- Treat human overlay text with the same escaping, redaction, and prompt-injection-as-data rules as repository text.
- Restrict MCP evidence access to the resolved repository root and known Evidence IDs.
- Treat repository text as data rather than instructions during extraction and validation.

## 15. Error handling

| Failure | Behavior |
|---|---|
| Not a Git repository | Stop preflight with a corrective message |
| CodeWiki missing or unsupported | Stop before LLM use and report the supported 0.6 series |
| Indexing failure | Preserve prior knowledge and return failed or partial |
| Model/provider failure | Apply bounded retry; publish nothing from the failed target |
| Malformed model output | Attempt schema repair at most twice |
| Missing or changed evidence | Mark affected objects stale |
| Conflicting evidence | Publish no verified replacement; record conflicted result |
| Compiler failure | Keep canonical IR; return partial and allow deterministic retry |
| Invalid or conflicting human overlay | Stop the affected build or update with typed overlay issues; never silently drop protected content |
| Interrupted run | Leave staging and report for diagnosis; canonical objects remain intact |

## 16. Edge-case behavior

| Repository condition | V0.1 behavior |
|---|---|
| Empty repository or no eligible source | Stop build before model use; create no misleading empty knowledge base |
| Git repository with no commit | Stop preflight and require an initial commit so scope can be versioned |
| Detached HEAD | Allow build using the commit; record branch as `null` and state as detached |
| Shallow clone | Allow inventory-based build/update without requiring unavailable history |
| Dirty working tree | Allow it; persist filtered working-tree hash and per-file hashes |
| Branch or non-descendant commit switch | Compare eligible-file inventories and refresh affected planning areas |
| Missing CodeWiki cache | Rebuild the provider index; use tracked inventory for change detection |
| Unsupported source language | Exclude unsupported files from semantic evidence, report coverage, and fail if no supported code remains |
| Repository exceeds configured file/byte limits | Stop with `scope_limit_exceeded` and require explicit path exclusions; do not silently publish partial coverage as complete |
| Symlink resolving outside repository root | Exclude it from scan and evidence access |
| Malformed or schema-invalid human overlay | Fail closed with typed overlay issues before regeneration; prior generations remain readable |
| Deleted evidence source | Mark every referencing canonical object stale until repaired or deliberately retired by a refreshed plan |

## 17. Implementation slices

The implementation plan must preserve this vertical order so the V0.1 scope does not become several parallel unfinished subsystems:

1. Blocking CodeWiki Adapter Spike with captured public-interface JSON fixtures and a go/no-go result.
2. Fake Provider vertical slice: one Module object through plan, extraction result, validation, canonical YAML, Markdown Card, and Wiki page.
3. CodeWiki adapter plus built-in LiteLLM mode for the same vertical slice.
4. All five object types, Claim-backed payload rules, and semantic verification.
5. Persisted RunOrchestrator plus Codex Skill execution mode and interruption recovery.
6. Tracked inventory, stale marking, pending-target retries, and selective update.
7. Human knowledge layer: overlay contracts, `knowledge edit`, regeneration preservation, conflict and retirement semantics.
8. HTML export, FTS task context, seven read-only MCP tools, human-layer rendering and exposure, and security boundary tests.
9. Agent A/B benchmark and product-gate report.

Failure of slice 1 blocks the remaining CodeWiki-based plan and returns the design for revision; it does not authorize importing CodeWiki internals.

## 18. Testing strategy

1. Unit tests for models, validators, ranking, budgets, and serializers.
2. YAML round-trip and schema compatibility tests.
3. EvidenceProvider contract tests with a fake provider and CodeWiki fixture adapter.
4. Golden tests for Wiki Markdown, Cards, Mermaid, and standalone HTML.
5. Incremental fixture tests for modified, added, deleted, renamed, dirty files, provider-index failure, stale-view policy, model-independent deterministic retirement, and inconclusive retirement checks.
6. CLI tests for the exact Agent lease/submission commands, progress summaries, exit codes, partial runs, idempotency, and interruption recovery.
7. MCP tests for all seven tools, repository-boundary enforcement, generation/snapshot mismatch fail-closed behavior, and explicit stale diagnostics.
8. Shared RunOrchestrator request/result contract tests using deterministic fake semantic workers and simulated Agent submissions.
9. Publish-journal crash tests at each canonical/plan/Card/FTS/manifest swap point, including startup recovery.
10. Human-layer tests: overlay schema round-trips, `knowledge edit` validation, preservation across incremental updates, field-override conflict fixtures, retirement archiving, and attribution plus escaping in every view, retrieval, and MCP path.
11. Opt-in live tests for Codex Skill and LiteLLM; CI does not require paid model calls.

## 19. Agent A/B benchmark

Run baseline and experimental agents on the same fixed repository commit, model, task, timeout, and tool permissions.

Baseline:

```text
Agent + repository
```

Experimental:

```text
Agent + repository + Knowledge Compiler
```

Tasks cover module explanation, end-to-end flow tracing, impact analysis, API parameter changes, business-rule changes, and a seeded bug fix.

Record task success, resulting code/tests, tool calls, read/search/grep counts, input and retrieved tokens, time to first valid edit, objects consumed, and knowledge-caused errors.

## 20. Acceptance criteria

### 20.1 Technical Definition of Done

- One local Git repository can complete build and update.
- Both execution modes satisfy the shared request/result contracts and RunOrchestrator state machine.
- All five object types can be generated.
- Every factual field is backed by verified Claims, and every required Claim contains Evidence references.
- Structural and semantic validation run successfully.
- Repo Wiki Markdown, standalone HTML, Cards, and task context compile.
- Protected human edits survive regeneration, surface conflicts explicitly, and render with attribution in Wiki, Cards, context, and MCP.
- Incremental invalidation and selective rebuild work on fixtures.
- CLI and all seven MCP tools are usable.
- Automated tests pass.
- The benchmark and its report are repeatable.

### 20.2 Product hypothesis gate

- Structural validity of Evidence IDs, paths, and line ranges is 100%.
- A manual sample of at least 50 claims has at least 90% source support.
- Critical Wiki conclusions have source citations.
- Agent task success improves, or success remains equivalent while repository-exploration tool calls decrease by at least 25%.
- Stale and conflicted knowledge never enters default task context.

Meeting the technical definition without meeting the product gate yields a completed experiment, not evidence to expand product scope. The next iteration must first address Evidence quality, IR design, validation, or context selection.

## 21. Evolution path

- V0.1: one local Git repository and the complete evidence-to-context loop, including the protected human knowledge layer.
- V0.1.x: Git URL RepositoryProvider, clone cache, branch selection, and private-repository credentials.
- V0.2: multi-repository workspaces and cross-repository flows.
- Later: human-content approval workflows and team governance of overlays, Git/PR decisions, issues/incidents, and non-code enterprise knowledge.

These future items influence interface boundaries but add no speculative implementation to V0.1.
