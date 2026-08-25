# RunOrchestrator and Two Execution Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Built-in LiteLLM and Codex Skill/Agent transports consume one persisted queue with recoverable leases, bounded retries, idempotency, and publication ownership, delivered through `knowledge build`/`knowledge validate` and the Agent queue CLI.

**Architecture:** A persisted `RunOrchestrator` owns the target state machine under `.knowledge/state/runs/<run-id>/`: targets move `queued → evidence_ready → extraction_leased → draft_submitted → structural_validated → semantic_pending → verification_leased → verified`, with `repair_pending` and terminal results `invalid | conflicted | insufficient_evidence | retired | skipped`. The orchestrator — never the worker or Skill — increments attempts, grants leases, schedules verification, decides publication eligibility, and computes final run status. Both transports submit identical semantic result schemas; the built-in executor drives `LiteLLMWorker` in-process against the queue.

**Tech Stack:** Python 3.12, Pydantic 2, Typer, pytest (injected clock and fake workers; no network in CI)

**Specs:** design §5.4, §9.3-9.7, §13; handoff M4.1-M4.8; the M2/M3 contracts.

---

## Scope and invariants

- Orchestrator owns retries, repair prompts, terminal status, publication eligibility, and generation publication; workers only map request→result.
- Both execution modes share request/result schemas, leases, idempotency, budgets, and anti-hallucination rules exactly.
- Extraction and verification keep separate leases, attempt counters, and idempotency domains even on one model profile.
- Duplicate submissions with the same idempotency key return the recorded result without repeating validation, model work, or publication.
- Expired leases return work to the prior queue state without losing accepted results.
- Per target: initial attempt plus at most two repair attempts.
- Store mutations are atomic and crash-recoverable; the clock is injected; secrets never enter `.knowledge/`, prompts, or reports.
- One active run at a time per repository: starting a run while a live run holds the state rejects with a typed error (advisory lock or startup rejection of a live run).
- No incremental/ChangeSet behavior (M5), human overlays (M6), views/FTS/MCP (M7).

## Planned file structure

```text
src/knowledge_compiler/
├── orchestrator/
│   ├── __init__.py
│   ├── contracts.py          # RunRecord, TargetRecord, Lease, state enums
│   ├── store.py              # atomic persisted queue + startup validation
│   ├── queue.py              # leases, attempts, idempotency replay
│   └── runner.py             # scheduling + publication ownership
├── workers/queue_executor.py # built-in transport over the queue
├── cli.py                    # + build/validate + agent queue commands
└── skills/knowledge-build/   # Skill artifacts (source archived in docs)
tests/orchestrator/           # state store, queue, runner, crash matrix
tests/cli/test_build.py, test_agent_queue.py
```

### Task 1 (M4.1): This plan

- [ ] Independent plan review; fix until approved; commit.

### Task 2 (M4.2): Persisted run, target, lease, and report contracts

- [ ] Failing tests: state-machine transitions (legal path and every illegal transition), terminal results, lease fields (run/target/operation/expiry/token/attempt/idempotency key), request/result digests, diagnostics, published object id; tampered/copied state rejected; injected clock (no wall time).
- [ ] Implement `orchestrator/contracts.py` + `store.py`: atomic writes under `.knowledge/state/runs/<run-id>/`, startup validation, impossible-transition rejection.
- [ ] Focused/full tests, reviews, commit `feat: persist orchestrator run state`.

### Task 3 (M4.3): Queue, leases, attempts, idempotency

- [ ] Failing tests: lease grant/exclusive/expiry/restart/stale token/wrong target-op-run; duplicate idempotent replay returns the recorded result; altered payload on replay rejected; expired work returns to queue keeping accepted results; attempt bound (initial + 2 repairs); separate extract/verify domains; crash-recoverable mutations; second concurrent run rejected while a live run holds the state.
- [ ] Implement `orchestrator/queue.py`.
- [ ] Focused/full tests, reviews, commit `feat: lease orchestrator work idempotently`.

### Task 4 (M4.4): Scheduling and publication ownership

- [ ] Failing tests: full pipeline preflight→plan→evidence→extraction→validation→verification→canonicalize→publish→status; one target failing publishes other verified objects with complete/partial/failed computed correctly; required-stale blocks complete, optional-insufficient completes with warnings; interrupted runs preserve previous generations (crash at every persisted state).
- [ ] Implement `orchestrator/runner.py` over the M2 providers/planner/worker seams and M3 typed publication.
- [ ] Focused/full tests, reviews, commit `feat: orchestrate runs end to end`.

### Task 5 (M4.5): Built-in executor transport

- [ ] Failing tests (fake worker/transport): queue-driven `LiteLLMWorker` execution receives exactly the target's pack/schema/budgets/identity; separate extract/verify conversations; cancellation, timeout, malformed repair, restart, duplicate completion.
- [ ] Implement `workers/queue_executor.py`.
- [ ] Focused/full tests, reviews, commit `feat: run the built-in executor over the queue`.

### Task 6 (M4.6): Agent-only queue CLI

- [ ] Implement `knowledge prepare | next --operation extraction | evidence <target> | submit-extraction <draft.json> --lease <token> | verify-next | submit-verification <result.json> --lease <token> | finalize` with help, JSON/Markdown output, invalid input, wrong lease, idempotent replay, interruption, sanitization, exit codes; hidden from primary help.
- [ ] `verify-next` serves ONLY a fresh verification request (Claim-backed fields plus cited redacted evidence, no extraction conversation reuse) per design §9.3; failing test that extraction-context-derived verification input is rejected or bounded.
- [ ] Focused/full tests, reviews, commit `feat: add the agent queue cli`.

### Task 7 (M4.7): `/knowledge-build` Codex Skill

- [ ] Create the Skill after the queue CLI is green: it only calls queue commands (no own scheduler/retries/validation bypass/publication), treats repository text as untrusted data, supports interruption/resumption; deterministic protocol tests; archive source under `docs/project-materials/03-skills/`.
- [ ] Focused/full tests, reviews, commit `feat: add the knowledge-build skill`.

### Task 8 (M4.8): `build`/`validate` CLI and exit gate

- [ ] Failing tests: `knowledge build --executor llm` exit 0 complete / 1 failed / 2 partial with the structured secrets-free run report under `state/runs/<run-id>/`; `knowledge validate` covering canonical store, plans, manifests, and view-generation consistency; preflight reports the validation-profile choice (reuse of the extraction profile with the separate verification prompt) per design §9.4.
- [ ] Implement both commands over the orchestrator.
- [ ] Prove Agent and built-in modes produce identical contract-level results from identical submissions; restart/expiry never duplicates publication; secrets audit over `.knowledge/`, prompts, reports, tests.
- [ ] Full suite ×2, CLI matrix, crash matrix, boundary scan, spec/quality/milestone reviews, push approved M4.

### Task 8b: M3 deferred harnesses and backlog polish

- [ ] Per-type extraction fixtures through the CodeWiki fixture provider (four harnesses) per the recorded M3 disposition, plus the M3-backlog items: wire resolved inventory counts into the scope-limit preflight stop and sanitize the realslice CLI's provider-construction failures.
- [ ] Focused/full tests, reviews, commit `feat: complete per-type fixture harnesses`.

## Completion checks

- [ ] Both execution modes share the persisted orchestrator and contracts.
- [ ] Expired/interrupted work resumes without duplicate publication.
- [ ] Extraction and verification remain separate even on one model.
- [ ] Every M4 CLI command has help, invalid-input, idempotency, interruption, and exit-code coverage.
- [ ] API keys never enter repository files, prompts, run reports, or `.knowledge/`.
