# CodeWiki Local Beta Product Design

**Status:** Approved baseline — 2026-09-17  
**Visual source:** [本地 Beta 设计定稿](../../design/2026-09-17-local-beta-design.html)  
**Durable decisions:** [D-026 / D-027](../../knowledge/product/decision-log.md)

## 1. Product goal

Turn the existing trustworthy knowledge compiler into a local product that one developer can install, operate, inspect, and connect to coding agents without a cloud server.

The complete journey is:

```text
install → preflight → add local repository → plan knowledge → build
        → inspect claims/evidence → ask → preview task context → use from agent
```

## 2. Users and deployment

- Primary user: an individual developer using local repositories and coding agents.
- Deployment: one local process group on one developer machine.
- Authority: each repository's canonical knowledge, evidence, overlays, manifest, and generation history remain under `.knowledge/`.
- Application state: repository registry, UI preferences, job projections, and diagnostics live in an OS-appropriate CodeWiki application-data directory.
- No cloud service, account system, tenant isolation, billing, or local/cloud synchronization in this release.
- The same core may be deployable elsewhere later, but no server architecture is built speculatively.

## 3. Product invariants

1. Evidence, knowledge, and context remain separate contracts.
2. Canonical knowledge is the only factual authority; Wiki, cards, FTS, HTML, and future vectors are projections.
3. Dirty or mismatched snapshots fail closed across Web, CLI, and MCP.
4. External parser crashes, timeouts, and malformed output never crash the local application process.
5. Degraded capability is shown explicitly; the product never labels a partial parse as complete.
6. Existing CLI behavior and deterministic exports remain backward compatible unless a recorded decision changes them.
7. Credentials remain environment/runtime inputs and never enter repository configuration, diagnostics, logs, or generated knowledge.
8. A major approved design is incomplete until README, docs index, design archive, and decision log agree.

## 4. Target architecture

```text
Local Web SPA ─┐
CLI ───────────┼─> Application Services ─> Canonical Compiler Pipeline
MCP ───────────┘          │                         │
                          ├─> Local API             ├─> .knowledge authority
                          ├─> Job supervisor        ├─> deterministic exports
                          └─> Read projections      └─> FTS/cache projections

External CodeWiki CLI ─> supervised child process ─> normalized EvidenceProvider
Fallback provider ──────────────────────────────────> degraded EvidenceProvider
```

### 4.1 Runtime boundaries

- `application/`: use cases shared by CLI, HTTP, and MCP; no presentation concerns.
- `app/`: FastAPI transport, local process lifecycle, stable error envelopes, SSE job events.
- `providers/`: capabilities, supervision, normalization, and fallback evidence.
- `web/`: React + TypeScript source; built assets are embedded into the Python wheel.
- `.knowledge/`: per-repository authority and rebuildable projections.
- application SQLite: repository registry and job/event projection only; never a second canonical knowledge store.

### 4.2 Local API contract

All application endpoints use `/api/v1`, Pydantic request/response models, and one error shape:

```json
{
  "error": {
    "code": "provider_crashed",
    "message": "Code parser exited unexpectedly",
    "action": "Retry with degraded evidence or view diagnostics",
    "details": {}
  }
}
```

Required surfaces:

- health, version, runtime capabilities, and redacted diagnostics;
- repository register/list/remove, snapshot, scope, and knowledge plan;
- build/update/compile jobs, lifecycle controls, events, targets, and diagnostics;
- overview, knowledge tree, object, claim, evidence, sources, history, and diff;
- Claim-level search, evidence-only Ask, and task-context preview;
- static export and backup metadata.

## 5. Data authority and storage

| Data | Store | Authority |
| --- | --- | --- |
| Repository snapshot | `.knowledge/state` | factual input |
| Evidence and canonical objects | `.knowledge/objects` + manifest | authoritative |
| Human overlays | `.knowledge/human` | authoritative human input |
| Run source records | `.knowledge/state/runs` | authoritative execution record |
| App repository/job projection | application SQLite | rebuildable operational projection |
| Claim FTS | `.knowledge/cache` SQLite | rebuildable search projection |
| Wiki/site/HTML | `.knowledge/exports` | rebuildable view |

Migrations must be forward-only, versioned, backed up before mutation, and tested from every released schema supported by Beta.

## 6. Human experience

Primary navigation:

```text
Overview / Knowledge Map / Ask / Build Jobs / Changes & History /
Data & Export / Settings & Diagnostics
```

Required states include empty, onboarding, preflight-blocked, indexing, building, partial, degraded, current, stale, conflicted, failed, cancelled, and recovery-required. Every non-current state provides a plain-language cause, impact, and safe next action.

Raw IDs, hashes, request digests, and provider payloads remain available in an audit drawer but are not the default reading hierarchy. A user must be able to move from repository overview to a claim and its source evidence within three primary interactions.

## 7. Ask and agent behavior

- Default Ask is evidence-only and returns claims, evidence anchors, object context, currentness, and match explanation.
- Optional model summaries are separate from retrieval, cite every material sentence, and fall back to evidence-only when support is insufficient.
- Web, CLI, and MCP invoke the same application service and return the same evidence set for the same repository snapshot, query, filters, and budget.
- Task Context shows included/excluded items and budget accounting before the user copies or sends it to an agent.

## 8. Quality and security requirements

- Supported runtime: Python 3.12+ on macOS and Linux.
- Local API binds to loopback by default and rejects remote binding without a future explicit security decision.
- Repository source is read, never executed.
- Parser child processes have time, output, and resource limits; cancellation terminates the full process group.
- All filesystem writes retain existing symlink, ancestry, atomicity, and fsync protections.
- Core Python coverage remains at least 88%; new application/API/provider modules target at least 90%; critical state machines require transition-complete tests.
- Frontend critical flows require component tests, Playwright keyboard/accessibility checks, and visual snapshots.
- Every milestone is demonstrated on at least one repository outside this project; M10 requires at least three repositories across Python, TypeScript, and C-family input.

## 9. Release boundaries

Included: local Web, CLI, MCP, real repository reliability, trustworthy knowledge, overlays/history, optional model use with visible cost, and reproducible M8 evaluation.

Excluded: cloud hosting, accounts, tenants, organization permissions, billing, continuous sync, organization-wide multi-repository graph, mobile/native desktop shells, mandatory vector storage, and uncited generative answers.

## 10. Milestone map

- M9: local product foundation.
- M10: reliable repository ingestion and parsing.
- M11: build-job lifecycle.
- M12: knowledge-reading Beta.
- M13: Ask and Agent surface parity.
- M14: real-value proof and local Beta release.

Each milestone exits only when implementation, user-visible behavior, real-repository evidence, automated regression, documentation, and README status are all updated.

