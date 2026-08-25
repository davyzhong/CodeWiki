# Five Knowledge Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Architecture, Module, Flow, Rule, and TechStack knowledge share stable Claim/Evidence semantics, validate without type-specific bypasses, cross-reference safely, and compile deterministically.

**Architecture:** Extract the M1 Module contracts into shared base models, then add four typed payloads that reuse the same Claim/Evidence/Scope/Provenance/Validity machinery unchanged. Every factual field is Claim-backed; semantic contracts (extraction/verification envelopes) generalize from Module to a typed target union; deterministic compilers extend YAML/Card/Wiki with Mermaid for architecture relations and flow steps. Cross-type relations validate against a registry of existing object identities and stay explicitly unresolved when targets are absent.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML, pytest

**Specs:**
- `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md` §6 (esp. 6.3 typed payloads), §9.5-9.6, §10
- `docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md` (M1 invariants)

---

## Scope and invariants

- The five types share one Claim/Evidence/verification model; no type-specific validation bypass is permitted.
- Canonical objects remain `verified` or `stale` only; invalid/conflicted/insufficient/retired/skipped stay target results.
- Stable semantic IDs keep `<type>.<domain>.<name>` with type-specific prefixes and per-type claim ID patterns.
- Every factual typed field references verified Claims; optional fields with unsupported Claims are dropped during repair, never published half-verified.
- Relations are typed predicates with validated source/target identities; unresolved targets are explicit and never fabricated.
- Extraction and verification remain separate, digest-bound operations for every type.
- Compilers accept only revalidated verified objects plus exactly correlated packs; Mermaid renders only from verified Claim-backed relationships/steps with every untrusted identifier and label escaped.
- Determinism: canonical ordering, permutation invariance, and byte-identical golden outputs for all five types.
- No orchestrator (M4), incremental lifecycle (M5), human overlays (M6), views/MCP (M7) enter this milestone.

## Required-vs-optional field map (per type, before code)

Each type defines its required factual fields (must be Claim-backed with `supported` verification) and optional fields (dropped during repair when their Claims are partial/unsupported — never published half-verified):

| Type | Required fields | Optional fields | Insufficient behavior | Conflicted behavior |
|---|---|---|---|---|
| Module (M1) | summary, responsibilities (≥1), public interfaces, dependencies | relations | `insufficient_evidence` target result | `conflicted` target result |
| Architecture | summary, components (≥1), system boundaries, typed relationships | component dependencies, responsibilities per component | `insufficient_evidence` | `conflicted` |
| Flow | summary, trigger, ordered steps (≥1 with stable IDs), participants | data/control transitions, failure paths | `insufficient_evidence` | `conflicted` |
| Rule | summary, statement, applicability | severity (closed-vocabulary presentation label per design §6.3), constraints, exceptions, related modules/flows | `insufficient_evidence` | `conflicted` |
| TechStack | summary, entries (≥1) with category and scope | version identity (explicit `unknown` when unproven), configuration evidence | `insufficient_evidence` | `conflicted` |

## Planned file structure

```text
src/knowledge_compiler/
├── contracts/
│   ├── base.py               # shared payload base extracted from Module
│   └── knowledge.py          # five typed payload models (+ Module re-export)
├── validation/
│   ├── shared.py             # type-independent structural/source validation
│   ├── flows.py / rules.py / tech_stack.py / architecture.py
├── compiler/
│   ├── mermaid.py            # escaped diagram compilation
│   └── typed.py              # YAML/Card/Wiki for the four new types
tests/
├── contracts/test_knowledge_base.py
├── validation/test_typed_validation.py
├── compiler/test_typed_outputs.py + golden fixtures
└── relations/test_cross_type_relations.py
```

### Task 1: Shared canonical base extraction (Module unchanged in behavior)

- [ ] Failing tests: `test_knowledge_base.py` asserting the shared `Scope`, `Claim`, `ClaimBackedText`, `Relation`, `Confidence`, `Provenance`, `Validity`, `EvidenceRef`, and `Conflict` models validate identically for all types and that the Module golden YAML round-trips unchanged (backward compatibility).
- [ ] Extract `_ContractModel`/`_ClaimBacked`/shared validators into `contracts/base.py`; Module re-uses them with zero byte drift in goldens. Generalize inline claim `evidence_ids` toward the shared `EvidenceRef` binding where backward-compatible, and keep `Conflict` as the shared cross-object conflict record used by relations (Task 6).
- [ ] Focused/full tests, reviews, commit `feat: extract shared canonical knowledge base`.

### Task 1b: Typed semantic envelopes

- [ ] Failing tests proving `ExtractionRequest/Result` and `VerificationRequest/Result` carry a typed draft/verification union: a Flow draft cannot enter a Module envelope, envelopes stay digest-bound, and the Module fixture path round-trips byte-identically.
- [ ] Generalize the four semantic contracts to the type union without type switches that bypass correlation; extend the M1 slice harness to a typed variant.
- [ ] Focused/full tests, reviews, commit `feat: generalize semantic envelopes across types`.

### Task 2: ArchitectureKnowledge

- [ ] Claim-backed components, boundaries, responsibilities, dependencies, typed relationships; per-type ID/claim patterns `architecture.<domain>.<name>`.
- [ ] Invalid tests: unsupported components/boundaries/edges, duplicate identities, unresolved mandatory references, cross-snapshot Claims.
- [ ] Deterministic Mermaid graph golden (identifiers/labels escaped; repository text cannot inject directives or extra edges).
- [ ] Focused/full tests, reviews, commit `feat: add architecture knowledge`.

### Task 3: FlowKnowledge

- [ ] Claim-backed trigger, ordered typed steps with stable step IDs, participants, data/control transitions, failure paths; deterministic step order independent of input ordering metadata where semantics allow.
- [ ] Reject missing participants, invalid step references, forbidden cycles, unsupported branches, unverified failure paths.
- [ ] Deterministic sequence-diagram Mermaid golden from verified fields only, with the same identifier/label escaping and directive-injection adversarial tests as Architecture.
- [ ] Focused/full tests, reviews, commit `feat: add flow knowledge`.

### Task 4: RuleKnowledge

- [ ] Claim-backed statement, severity, applicability, constraints, exceptions, related modules/flows; normative repository facts distinguished from presentation labels.
- [ ] Reject rules inferred only from names/conventions, unsupported applicability, contradictory exceptions, conflicted evidence.
- [ ] Deterministic Rule Card/Wiki with evidence pointers; a test asserts every rendered line derives from payload fields or fixed templates (no unsupported prose).
- [ ] Focused/full tests, reviews, commit `feat: add rule knowledge`.

### Task 5: TechStackKnowledge

- [ ] Technology/package/configuration entries with category, version identity, scope, Claim/Evidence bindings; exact package/config evidence required for version claims; unknown versions explicit, never guessed.
- [ ] Reject dependency lock/config inconsistencies, unsupported versions, duplicate aliases, cross-snapshot evidence.
- [ ] Deterministic YAML/Card/Wiki goldens, plus technology relation diagrams when relation data is present (same escaping rules).
- [ ] Focused/full tests, reviews, commit `feat: add tech-stack knowledge`.

### Task 6: Cross-type relations and conflicts

- [ ] Typed predicate + source/target type combination table; relation validation against a registry of existing object IDs and snapshot identity.
- [ ] Missing targets remain explicitly unresolved; inbound/outbound indexes are deterministic projections, not new facts.
- [ ] Fixtures for unresolved references, conflicting Claims across objects, relation cycles, missing targets, later resolution.
- [ ] Conflicted/invalid/insufficient targets never become canonical or enter compiled Agent views.
- [ ] Focused/full tests, reviews, commit `feat: add cross-type relations`.

### Task 7: Five-type integration and exit gate

- [ ] All five types run through BOTH the fake-fixture and the CodeWiki fixture providers, extraction, separate verification, canonicalization, and publication (extending the M1 slice harness patterns; the shared provider contract suite gains per-type cases).
- [ ] Prove every factual payload field is Claim-backed or deterministically derived; all YAML/Card/Wiki/Mermaid golden-tested and permutation-invariant.
- [ ] Schema compatibility and round-trip tests for existing Module goldens.
- [ ] Full suite ×2, boundary scan, diff check, spec/quality reviews, the M3.8 security review, milestone-wide review, push approved M3.

## Completion checks

- [ ] Five types round-trip and compile deterministically.
- [ ] No type-specific validation bypass exists.
- [ ] Cross-object relations are typed, validated, and safely unresolved when targets are absent.
- [ ] Invalid, conflicted, and insufficient-evidence results never become canonical objects.
