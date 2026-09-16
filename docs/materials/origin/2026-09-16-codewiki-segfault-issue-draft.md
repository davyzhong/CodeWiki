---
status: draft（issue 草稿，发布需用户确认——公开发布红线）
created: 2026-09-16
target: PorunC/CodeWiki（GitHub issue）
---

# `codewiki analyze` segfaults (SIGSEGV/SIGBUS) on real-world mid-sized Python repositories

## Environment

- macOS 15 (darwin 25.5.0, arm64)
- CPython 3.13.15 (Homebrew)
- codewiki 0.6.5 (PyPI)
- py-tree-sitter 0.26.0, tree-sitter-python 0.25.0 (codewiki's resolution)
- Reproduced with both the CLI and direct parser calls, single- and multi-threaded

## Symptom

`codewiki analyze <repo> --json` crashes the interpreter with a native signal and zero output on real-world mid-sized Python repos. Reproduced on: `psf/requests`, `jd/tenacity`, `hynek/structlog`, `pallets/click`, `julian/jsonschema` (all shallow clones, `analyze` exit 138/139). Small fixture repos (~10 files) and an 84-file synthetic repo pass.

The crash is **nondeterministic in signal but deterministic in occurrence**: over 50 fresh subprocess runs of a single-file direct parse, 50/50 crashed — 28× SIGSEGV (signal 11), 22× SIGBUS (signal 10). The mixed-signal pattern on identical input suggests memory corruption (UB) rather than a deterministic logic bug.

## Minimal reproduction

Delta-debugged from `psf/requests/src/requests/models.py` (1184 lines) down to a **258-line syntactically valid** file that keeps crashing: [`codewiki-segfault-repro-258.py`](codewiki-segfault-repro-258.py) (excerpted from psf/requests, Apache-2.0). Note the file keeps the module import block, `TYPE_CHECKING`, `Final`-annotated module constants, and the `@overload`/`@staticmethod` stack on `RequestEncodingMixin._encode_params`; smaller hand-written snippets with just those decorators do **not** trigger it, so the trigger is structural, not a single syntax pattern.

Direct single-file reproduction (no CLI, no cache, no threads):

```python
from pathlib import Path
from backend.app.services.ast_parsers.python import PythonAstParser

parser = PythonAstParser()
symbols = parser.parse(Path("codewiki-segfault-repro-258.py"), repo_root=Path("."))
```

```
$ for i in $(seq 50); do python repro.py >/dev/null 2>&1; echo $?; done | sort | uniq -c
  22    138   # SIGBUS
  28    139   # SIGSEGV
```

## Fault-handler stacks (two variants observed)

CLI path (threads on or off — same frame):

```
Current thread (most recent call first):
  dataclasses.py:1412 in _asdict_inner
  dataclasses.py:1429 in _asdict_inner
  dataclasses.py:1419 in _asdict_inner
  dataclasses.py:1408 in asdict
  backend/app/services/ast_cache.py:52 in write
  backend/app/services/ast_parsers/registry.py:103 in parse_file
  backend/app/services/ast_parser.py:122 in _parse_one_file
```

Forcing a single worker (`_parse_worker_count -> 1`, sequential path) crashes at the same frame, so this is **not** a thread-race between workers.

`AstSymbol` fields are all plain `str`/`int`/`list`/`dict`, which points the corruption at the tree-sitter layer below (query captures / node lifetimes) rather than the dataclass itself.

## Suggested directions

- Reproduce under `PYTHONMALLOC=malloc` and/or a debug build to pin the corruption site.
- Check py-tree-sitter 0.26.0 + CPython 3.13 combination (memory-safety of node capture lifetimes during query iteration).
- Consider guarding `ast_cache.write` (serialize symbols to plain types before crossing the C boundary), though the single-file repro crashes before any cache write, so the root likely sits in the capture engine.

## Impact

This blocks indexing of real-world repositories (the primary use case) on this platform/interpreter combination. Workaround attempts (single-threaded parse) do not help.
