# CodeWiki Public-Surface Adapter Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove whether CodeWiki 0.6.x public CLI, MCP, or HTTP surfaces can supply every fact required by the Knowledge Compiler `EvidenceProvider` contract without importing CodeWiki internals or reading its database.

**Architecture:** Build a disposable probe around a committed miniature Python repository. The probe records raw public-surface observations, normalizes capability evidence, and writes a deterministic Go/No-Go report. CLI is tested first; MCP is tested only for capabilities missing from CLI. Product feature work is blocked until this plan yields `decision: go`.

**Tech Stack:** Python 3.12, uv, Pydantic 2, pytest, Typer, official MCP Python SDK, Git CLI, CodeWiki 0.6.x

**Spec:** `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md`

## Global Constraints

- Target Python 3.12 and CodeWiki `>=0.6,<0.7`.
- Use only documented CodeWiki CLI, MCP, or HTTP surfaces.
- Never import `backend.*`, `codewiki.*` implementation modules, or query CodeWiki SQLite/PostgreSQL tables.
- Never execute source code, tests, build scripts, or dependency installation from the probe repository.
- Keep `.knowledge/`, `.codewiki/`, `.git/`, dependencies, binaries, and oversize files outside the eligible source inventory.
- Raw observations go under ignored `work/codewiki-spike/`; only sanitized contract fixtures and the decision report enter Git.
- Do not begin Knowledge IR, compiler, orchestration, or MCP product implementation in this plan.
- A missing or ambiguous capability produces `decision: no_go`; it must not be patched by accessing CodeWiki internals.

---

## Planned file structure

```text
pyproject.toml                              # Package metadata and spike-only dependencies
src/knowledge_compiler/__init__.py         # Package version
src/knowledge_compiler/spikes/
├── __init__.py                            # Spike package marker
├── fixture_repo.py                        # Materialize and commit the deterministic probe repository
├── observations.py                        # Command/MCP observation data models and sanitization
├── cli_probe.py                           # CodeWiki CLI runner
├── mcp_probe.py                           # Public MCP fallback runner
├── evaluator.py                           # Required-capability evaluation and decision model
└── main.py                                # Typer entry point and report orchestration
tests/
├── fixtures/probe_repo/                   # Static source tree copied into a temporary Git repo
│   ├── pyproject.toml
│   └── src/shop/
│       ├── __init__.py
│       ├── api.py
│       ├── checkout.py
│       └── inventory.py
├── spikes/
│   ├── test_fixture_repo.py
│   ├── test_observations.py
│   ├── test_cli_probe.py
│   ├── test_mcp_probe.py
│   └── test_evaluator.py
└── support/fake_codewiki.py               # Deterministic fake executable for unit tests
tests/fixtures/codewiki/0.6/               # Sanitized live public-surface JSON fixtures
docs/spikes/codewiki-public-surface.md      # Generated Go/No-Go evidence report
work/codewiki-spike/                        # Ignored raw live observations
```

## Required capability matrix

The evaluator must require all rows before returning `go`:

| Capability | Minimum observable evidence |
|---|---|
| Version | Parseable CodeWiki version in the 0.6 minor series |
| Repository registration | Public surface returns a stable repository identifier or unambiguous path identity |
| Full indexing | Public surface reports successful analysis for the committed probe snapshot |
| Repository survey | Eligible file paths and detected Python language are machine-readable |
| Symbols | `CheckoutService.checkout` and `Inventory.reserve` are machine-readable with source paths/ranges |
| Imports | The local import from checkout to inventory is observable |
| Calls | The call from checkout to `Inventory.reserve` is observable, with confidence/provenance when supplied |
| Source references | At least path, start line, and end line are available for a selected symbol |
| Topic exploration | A bounded query for `checkout inventory` returns relevant nodes or source references |
| Affected files/symbols | Supplying `src/shop/inventory.py` returns an affected result that includes checkout or its caller relationship |
| Incremental catch-up | After a non-executed source edit, public update succeeds and the new snapshot is queryable |
| Bounded machine output | The selected surface returns parseable JSON or MCP structured content without scraping human terminal text |

---

### Task 1: Bootstrap the spike harness and deterministic Git fixture

**Files:**
- Create: `pyproject.toml`
- Create: `src/knowledge_compiler/__init__.py`
- Create: `src/knowledge_compiler/spikes/__init__.py`
- Create: `src/knowledge_compiler/spikes/fixture_repo.py`
- Create: `tests/fixtures/probe_repo/pyproject.toml`
- Create: `tests/fixtures/probe_repo/src/shop/__init__.py`
- Create: `tests/fixtures/probe_repo/src/shop/api.py`
- Create: `tests/fixtures/probe_repo/src/shop/checkout.py`
- Create: `tests/fixtures/probe_repo/src/shop/inventory.py`
- Create: `tests/spikes/test_fixture_repo.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: none
- Produces: `materialize_probe_repo(template: Path, destination: Path) -> ProbeRepository`
- Produces: `ProbeRepository(root: Path, commit: str, eligible_files: tuple[str, ...])`

- [ ] **Step 1: Add the minimal package configuration**

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "knowledge-compiler"
version = "0.1.0.dev0"
requires-python = ">=3.12"
dependencies = [
  "mcp>=1.0",
  "pydantic>=2.10",
  "typer>=0.15",
]

[project.optional-dependencies]
dev = [
  "codewiki>=0.6,<0.7",
  "pytest>=8.3",
  "pytest-cov>=6.0",
]

[project.scripts]
knowledge-codewiki-spike = "knowledge_compiler.spikes.main:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.hatch.build.targets.wheel]
packages = ["src/knowledge_compiler"]
```

Add `__version__ = "0.1.0.dev0"` to `src/knowledge_compiler/__init__.py`, and leave `spikes/__init__.py` empty.

- [ ] **Step 2: Add the static probe repository**

`tests/fixtures/probe_repo/src/shop/inventory.py`:

```python
class Inventory:
    def reserve(self, sku: str, quantity: int) -> bool:
        return bool(sku) and quantity > 0
```

`tests/fixtures/probe_repo/src/shop/checkout.py`:

```python
from shop.inventory import Inventory


class CheckoutService:
    def __init__(self, inventory: Inventory) -> None:
        self.inventory = inventory

    def checkout(self, sku: str, quantity: int) -> str:
        if not self.inventory.reserve(sku, quantity):
            raise ValueError("inventory reservation failed")
        return "order-created"
```

`tests/fixtures/probe_repo/src/shop/api.py`:

```python
from shop.checkout import CheckoutService
from shop.inventory import Inventory


def checkout_order(sku: str, quantity: int) -> str:
    return CheckoutService(Inventory()).checkout(sku, quantity)
```

`tests/fixtures/probe_repo/src/shop/__init__.py` is empty. The fixture `pyproject.toml` contains:

```toml
[project]
name = "codewiki-probe-shop"
version = "0.0.0"
requires-python = ">=3.12"
```

- [ ] **Step 3: Write the failing fixture-materialization test**

```python
from pathlib import Path
import subprocess

from knowledge_compiler.spikes.fixture_repo import materialize_probe_repo


def test_materialize_probe_repo_creates_committed_snapshot(tmp_path: Path) -> None:
    template = Path("tests/fixtures/probe_repo")
    repo = materialize_probe_repo(template, tmp_path / "probe")

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo.root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    assert repo.commit == head
    assert repo.eligible_files == (
        "pyproject.toml",
        "src/shop/__init__.py",
        "src/shop/api.py",
        "src/shop/checkout.py",
        "src/shop/inventory.py",
    )
```

- [ ] **Step 4: Run the test and verify it fails**

Run: `uv run pytest tests/spikes/test_fixture_repo.py -v`

Expected: FAIL because `knowledge_compiler.spikes.fixture_repo` does not exist.

- [ ] **Step 5: Implement repository materialization**

```python
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class ProbeRepository:
    root: Path
    commit: str
    eligible_files: tuple[str, ...]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def materialize_probe_repo(template: Path, destination: Path) -> ProbeRepository:
    shutil.copytree(template, destination)
    _git(destination, "init", "-q")
    _git(destination, "config", "user.name", "Knowledge Compiler Spike")
    _git(destination, "config", "user.email", "spike@example.invalid")
    _git(destination, "add", ".")
    _git(destination, "commit", "-q", "-m", "fixture: initial repository")
    files = tuple(
        line
        for line in _git(destination, "ls-files").splitlines()
        if line and not line.startswith((".knowledge/", ".codewiki/"))
    )
    return ProbeRepository(destination, _git(destination, "rev-parse", "HEAD"), files)
```

- [ ] **Step 6: Ignore raw spike output and verify the test passes**

Add to `.gitignore`:

```gitignore
work/
.coverage
.pytest_cache/
__pycache__/
*.pyc
```

Run: `uv run pytest tests/spikes/test_fixture_repo.py -v`

Expected: PASS.

- [ ] **Step 7: Commit the fixture harness**

```bash
git add pyproject.toml src/knowledge_compiler tests/fixtures tests/spikes/test_fixture_repo.py .gitignore
git commit -m "test: add deterministic CodeWiki probe repository"
```

---

### Task 2: Model and sanitize public-surface observations

**Files:**
- Create: `src/knowledge_compiler/spikes/observations.py`
- Create: `tests/spikes/test_observations.py`

**Interfaces:**
- Consumes: `ProbeRepository`
- Produces: `CommandObservation`, `McpObservation`, `ProbeBundle`
- Produces: `sanitize_text(text: str, repo_root: Path) -> str`
- Produces: `write_bundle(bundle: ProbeBundle, path: Path) -> None`

- [ ] **Step 1: Write failing tests for path and secret sanitization**

```python
from pathlib import Path

from knowledge_compiler.spikes.observations import sanitize_text


def test_sanitize_text_replaces_repo_path_and_api_key() -> None:
    root = Path("/private/tmp/probe")
    value = "path=/private/tmp/probe/src/app.py api_key=sk-secret-value"

    sanitized = sanitize_text(value, root)

    assert sanitized == "path=<REPO>/src/app.py api_key=<REDACTED>"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/spikes/test_observations.py -v`

Expected: FAIL because `observations.py` does not exist.

- [ ] **Step 3: Implement the observation models and sanitizer**

```python
from pathlib import Path
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandObservation(BaseModel):
    name: str
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    json_value: Any | None = None


class McpObservation(BaseModel):
    name: str
    tool_name: str
    arguments: dict[str, Any]
    is_error: bool
    structured_content: Any | None = None
    text_content: list[str] = []


class ProbeBundle(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    codewiki_version: str | None
    repository_commit: str
    commands: list[CommandObservation]
    mcp: list[McpObservation] = Field(default_factory=list)


SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s]+)")


def sanitize_text(text: str, repo_root: Path) -> str:
    sanitized = text.replace(str(repo_root), "<REPO>")
    return SECRET_PATTERN.sub(r"\1<REDACTED>", sanitized)


def write_bundle(bundle: ProbeBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
```

- [ ] **Step 4: Add round-trip tests and run them**

Add a test that constructs a `ProbeBundle`, writes it with `write_bundle`, reloads the JSON, and asserts `schema_version == "0.1"` and no absolute repository path remains.

Run: `uv run pytest tests/spikes/test_observations.py -v`

Expected: PASS.

- [ ] **Step 5: Commit observation capture**

```bash
git add src/knowledge_compiler/spikes/observations.py tests/spikes/test_observations.py
git commit -m "feat: add sanitized CodeWiki probe observations"
```

---

### Task 3: Probe the documented CodeWiki CLI surface

**Files:**
- Create: `src/knowledge_compiler/spikes/cli_probe.py`
- Create: `tests/support/fake_codewiki.py`
- Create: `tests/spikes/test_cli_probe.py`

**Interfaces:**
- Consumes: `ProbeRepository`, CodeWiki executable path
- Produces: `run_cli_probe(executable: str, repo: ProbeRepository) -> list[CommandObservation]`

- [ ] **Step 1: Write a fake CodeWiki executable**

The fake script must inspect `sys.argv[1:]` and emit JSON for these command families: version, repository add, analyze, scan, graph search/explore/affected, and update. It returns exit code 2 for unknown commands. Use only fixture paths supplied in arguments; do not read production files.

```python
#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("codewiki 0.6.5")
elif args[:2] == ["repos", "add"]:
    print(json.dumps({"repository": {"id": "probe-repo", "path": args[2]}}))
elif args and args[0] == "analyze":
    print(json.dumps({"status": "completed", "repository_id": "probe-repo"}))
elif args[:2] == ["repos", "scan"]:
    print(json.dumps({"files": [
        {"path": "src/shop/checkout.py", "language": "python"},
        {"path": "src/shop/inventory.py", "language": "python"}
    ]}))
elif args[:2] == ["graph", "search"]:
    print(json.dumps({"nodes": [{"name": "CheckoutService", "path": "src/shop/checkout.py"}]}))
elif args[:2] == ["graph", "explore"]:
    print(json.dumps({"nodes": [], "edges": [], "sources": []}))
elif args[:2] == ["graph", "affected"]:
    print(json.dumps({"affected": ["src/shop/checkout.py"]}))
elif args and args[0] == "update":
    print(json.dumps({"status": "completed"}))
else:
    print(json.dumps({"error": "unsupported", "args": args}))
    raise SystemExit(2)
```

- [ ] **Step 2: Write the failing CLI probe test**

```python
from pathlib import Path

from knowledge_compiler.spikes.cli_probe import run_cli_probe
from knowledge_compiler.spikes.fixture_repo import materialize_probe_repo


def test_run_cli_probe_records_every_documented_command(tmp_path: Path) -> None:
    repo = materialize_probe_repo(Path("tests/fixtures/probe_repo"), tmp_path / "repo")
    observations = run_cli_probe("tests/support/fake_codewiki.py", repo)

    names = {item.name for item in observations}
    assert {
        "version", "repos_add", "analyze", "repos_scan",
        "graph_search", "graph_explore", "graph_affected", "update",
    } <= names
    assert all(item.json_value is not None or item.name == "version" for item in observations)
```

- [ ] **Step 3: Run the test and verify it fails**

Run: `chmod +x tests/support/fake_codewiki.py && uv run pytest tests/spikes/test_cli_probe.py -v`

Expected: FAIL because `cli_probe.py` does not exist.

- [ ] **Step 4: Implement the CLI runner**

Implement one private `_run()` that executes with `shell=False`, a 120-second timeout, captured text output, and an explicit environment. It must parse stdout as JSON when possible and always record failure observations rather than raising for non-zero CodeWiki exit codes.

The public probe runs these documented candidates in order:

```python
commands = [
    ("version", ["--version"]),
    ("repos_add", ["repos", "add", str(repo.root), "--json"]),
    ("analyze", ["analyze", str(repo.root), "--json"]),
    ("repos_scan", ["repos", "scan", str(repo.root), "--json"]),
    ("graph_search", ["graph", "search", "CheckoutService", "--repo", str(repo.root), "--json"]),
    ("graph_explore", ["graph", "explore", "checkout inventory", "--repo", str(repo.root), "--json"]),
]
```

For affected analysis, send `src/shop/inventory.py\n` to stdin using:

```python
["graph", "affected", "--repo", str(repo.root), "--stdin", "--json"]
```

Then append a comment-only line to `src/shop/inventory.py`, run:

```python
["update", str(repo.root), "--json"]
```

and repeat graph search as `graph_search_after_update`. Do not import or execute any code from the probe repository.

- [ ] **Step 5: Run CLI tests and verify behavior**

Run: `uv run pytest tests/spikes/test_cli_probe.py -v`

Expected: PASS with the fake executable. A non-zero fake response must remain in the observation list with its stderr and return code.

- [ ] **Step 6: Commit the CLI probe**

```bash
git add src/knowledge_compiler/spikes/cli_probe.py tests/support/fake_codewiki.py tests/spikes/test_cli_probe.py
git commit -m "feat: probe CodeWiki public CLI capabilities"
```

---

### Task 4: Add MCP fallback discovery without coupling to CodeWiki internals

**Files:**
- Create: `src/knowledge_compiler/spikes/mcp_probe.py`
- Create: `tests/spikes/test_mcp_probe.py`

**Interfaces:**
- Consumes: CodeWiki executable, `ProbeRepository`, missing CLI capability names
- Produces: `run_mcp_probe(executable: str, repo: ProbeRepository, required: set[str]) -> list[McpObservation]`

- [ ] **Step 1: Write a failing tool-selection test**

```python
from knowledge_compiler.spikes.mcp_probe import select_tools


def test_select_tools_matches_public_capabilities() -> None:
    tools = [
        "codewiki_graph_search",
        "codewiki_graph_explore",
        "codewiki_graph_affected",
        "codewiki_files",
    ]
    selected = select_tools(tools, {"symbols", "topic_exploration", "affected"})

    assert selected == {
        "symbols": "codewiki_graph_search",
        "topic_exploration": "codewiki_graph_explore",
        "affected": "codewiki_graph_affected",
    }
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/spikes/test_mcp_probe.py -v`

Expected: FAIL because `mcp_probe.py` does not exist.

- [ ] **Step 3: Implement deterministic public-tool selection**

```python
TOOL_CANDIDATES = {
    "survey": ("codewiki_files", "codewiki_indexed_files"),
    "symbols": ("codewiki_graph_search", "codewiki_search"),
    "topic_exploration": ("codewiki_graph_explore", "codewiki_context"),
    "affected": ("codewiki_graph_affected", "codewiki_affected"),
    "source_references": ("codewiki_node", "codewiki_graph_search"),
}


def select_tools(available: list[str], required: set[str]) -> dict[str, str]:
    available_set = set(available)
    return {
        capability: next(name for name in TOOL_CANDIDATES[capability] if name in available_set)
        for capability in sorted(required)
        if any(name in available_set for name in TOOL_CANDIDATES[capability])
    }
```

- [ ] **Step 4: Implement MCP list/call orchestration**

Use the official SDK's stdio client with server command `codewiki` and arguments `mcp --lite --path <repo>`. Call `session.initialize()`, then `session.list_tools()`. Only call selected tools for CLI-missing capabilities. Use these bounded arguments:

```python
arguments = {
    "survey": {"path": str(repo.root)},
    "symbols": {"query": "CheckoutService", "limit": 10},
    "topic_exploration": {"query": "checkout inventory", "max_hops": 2},
    "affected": {"files": ["src/shop/inventory.py"]},
    "source_references": {"query": "Inventory.reserve", "limit": 10},
}
```

If a discovered tool rejects an argument shape, record the structured MCP error and retry once using only fields declared by the tool's `inputSchema`. Never scrape text to invent missing fields.

- [ ] **Step 5: Test with a fake MCP session**

Create an in-test fake session exposing `list_tools()` and `call_tool()`; assert the probe calls only required capabilities, applies `limit <= 10`, and records structured content and errors.

Run: `uv run pytest tests/spikes/test_mcp_probe.py -v`

Expected: PASS.

- [ ] **Step 6: Commit MCP fallback discovery**

```bash
git add src/knowledge_compiler/spikes/mcp_probe.py tests/spikes/test_mcp_probe.py
git commit -m "feat: add CodeWiki MCP capability fallback"
```

---

### Task 5: Evaluate capabilities and generate the Go/No-Go report

**Files:**
- Create: `src/knowledge_compiler/spikes/evaluator.py`
- Create: `src/knowledge_compiler/spikes/main.py`
- Create: `tests/spikes/test_evaluator.py`

**Interfaces:**
- Consumes: `ProbeBundle`
- Produces: `CapabilityResult`, `SpikeDecision`
- Produces: `evaluate(bundle: ProbeBundle) -> SpikeDecision`
- Produces: CLI `knowledge-codewiki-spike run --repo-template ... --work-dir ... --report ...`

- [ ] **Step 1: Define evaluator examples as failing tests**

```python
from knowledge_compiler.spikes.evaluator import evaluate
from knowledge_compiler.spikes.observations import ProbeBundle


def test_evaluate_returns_no_go_when_calls_are_missing(complete_bundle_dict: dict) -> None:
    bundle = ProbeBundle.model_validate(complete_bundle_dict)
    for command in bundle.commands:
        if command.name == "graph_explore":
            command.json_value = {"nodes": [], "edges": [], "sources": []}
    decision = evaluate(bundle)

    assert decision.decision == "no_go"
    assert "calls" in decision.missing_capabilities


def test_evaluate_returns_go_for_complete_public_contract(complete_bundle_dict: dict) -> None:
    decision = evaluate(ProbeBundle.model_validate(complete_bundle_dict))

    assert decision.decision == "go"
    assert decision.missing_capabilities == []
```

The `complete_bundle_dict` fixture must contain explicit machine-readable files, symbols, imports, calls, source ranges, topic hits, affected results, and post-update results. Do not use a blanket `success: true` fixture.

- [ ] **Step 2: Run the evaluator tests and verify they fail**

Run: `uv run pytest tests/spikes/test_evaluator.py -v`

Expected: FAIL because `evaluator.py` does not exist.

- [ ] **Step 3: Implement capability evidence extraction**

Create one evaluator function per capability. Each returns evidence references into the bundle, not prose guesses:

```python
CAPABILITIES = (
    "version",
    "repository_registration",
    "full_index",
    "repository_survey",
    "symbols",
    "imports",
    "calls",
    "source_references",
    "topic_exploration",
    "affected",
    "incremental_update",
    "bounded_machine_output",
)
```

`SpikeDecision.decision` is `go` only when every `CapabilityResult.status == "supported"`. `ambiguous`, `missing`, provider error, or human-text-only output all map to `no_go`.

- [ ] **Step 4: Implement the CLI orchestration**

The `run` command must:

1. materialize a fresh committed probe repository under the work directory;
2. execute the CLI probe;
3. evaluate preliminary missing capabilities;
4. execute MCP fallback only for those missing capabilities;
5. evaluate the merged bundle;
6. write sanitized raw bundle JSON under the work directory;
7. write a Markdown decision report with version, command table, capability table, missing capabilities, selected public surface, and exact decision;
8. exit `0` for `go`, `2` for `no_go`, and `1` for probe infrastructure failure.

Use this report header and ensure every section is populated from models:

```markdown
# CodeWiki Public-Surface Spike

- CodeWiki version: `<sanitized value>`
- Probe repository commit: `<fixture commit>`
- Decision: `go|no_go`

## CLI observations
## MCP fallback observations
## Capability matrix
## Missing or ambiguous capabilities
## Adapter recommendation
```

- [ ] **Step 5: Run all unit tests**

Run: `uv run pytest tests/spikes -v`

Expected: PASS with no real CodeWiki process required.

- [ ] **Step 6: Commit the evaluator and entry point**

```bash
git add src/knowledge_compiler/spikes/evaluator.py src/knowledge_compiler/spikes/main.py tests/spikes/test_evaluator.py
git commit -m "feat: evaluate CodeWiki adapter go-no-go gate"
```

---

### Task 6: Run the live CodeWiki 0.6 spike and freeze the public contract

**Files:**
- Create: `tests/fixtures/codewiki/0.6/cli-observations.json`
- Create: `tests/fixtures/codewiki/0.6/mcp-observations.json` when MCP fallback is used
- Create: `docs/spikes/codewiki-public-surface.md`
- Modify: `tests/spikes/test_cli_probe.py`
- Modify: `tests/spikes/test_mcp_probe.py` when MCP fallback is used

**Interfaces:**
- Consumes: Tasks 1-5 and an installed CodeWiki 0.6.x executable
- Produces: sanitized compatibility fixtures and a definitive `go` or `no_go` report
- Gate: product implementation planning proceeds only for `go`

- [ ] **Step 1: Install the isolated development environment**

Run:

```bash
uv sync --extra dev
uv run codewiki --version
```

Expected: CodeWiki reports a version in the 0.6 minor series. If installation or version validation fails, record an infrastructure failure and stop this task.

- [ ] **Step 2: Run the live probe**

```bash
uv run knowledge-codewiki-spike run \
  --repo-template tests/fixtures/probe_repo \
  --work-dir work/codewiki-spike/live-0.6 \
  --report docs/spikes/codewiki-public-surface.md
```

Expected: exit `0` with `Decision: go`, or exit `2` with a complete `Decision: no_go` report. Both are valid spike outcomes; only `go` authorizes the next product plan.

- [ ] **Step 3: Inspect raw observations for secrets and unstable paths**

Run:

```bash
rg -n "/Users/|/private/|api[_-]?key|sk-[A-Za-z0-9]" work/codewiki-spike/live-0.6 docs/spikes/codewiki-public-surface.md
```

Expected: no secret value and no absolute user path. Sanitized labels such as `<REPO>` and `<REDACTED>` are allowed.

- [ ] **Step 4: Freeze sanitized public contract fixtures**

Copy only the sanitizer-approved CLI and MCP observation models into `tests/fixtures/codewiki/0.6/`. Add regression tests that load these fixtures and assert `evaluate(...)` returns the same decision recorded in the report.

Run: `uv run pytest tests/spikes -v`

Expected: PASS against both fake and captured public-surface fixtures.

- [ ] **Step 5: Verify the public-boundary rule mechanically**

Run:

```bash
rg -n "from (backend|codewiki)\.|import (backend|codewiki)|sqlite3|aiosqlite|SELECT .*code_(node|edge|chunk)" src tests
```

Expected: no matches in implementation code. Mentions inside captured help/output fixtures may be reviewed manually and must not correspond to executable imports or queries.

- [ ] **Step 6: Run the full verification suite**

```bash
uv run pytest -v
git diff --check
git status --short
```

Expected: all tests pass, diff check is clean, and only intended spike fixtures/report changes remain.

- [ ] **Step 7: Commit the live decision**

For a Go result:

```bash
git add tests/fixtures/codewiki/0.6 docs/spikes/codewiki-public-surface.md tests/spikes
git commit -m "test: verify CodeWiki 0.6 public adapter contract"
```

For a No-Go result:

```bash
git add tests/fixtures/codewiki/0.6 docs/spikes/codewiki-public-surface.md tests/spikes
git commit -m "docs: record CodeWiki public adapter no-go"
```

- [ ] **Step 8: Apply the gate**

If the report says `go`, create the next implementation plan from the captured normalized DTO shapes, beginning with the Fake Provider vertical slice in design section 17.

If it says `no_go`, stop. Present the exact missing capabilities to the user and return the approved design for revision. Do not import CodeWiki internals, read its database, or start Knowledge IR implementation.

---

## Plan completion checks

- [ ] Every required CodeWiki capability has direct public-surface evidence or is listed missing.
- [ ] The decision is derived from the evaluator and reproducible from committed sanitized fixtures.
- [ ] Absolute paths, credentials, raw caches, and databases are absent from Git.
- [ ] No CodeWiki implementation import or database query exists.
- [ ] `pytest`, `git diff --check`, and the boundary scan pass.
- [ ] The next plan is created only after a `go` decision.
