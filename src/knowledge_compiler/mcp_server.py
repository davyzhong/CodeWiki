from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "knowledge-compiler"
SERVER_VERSION = "0.1"

TOOL_NAMES = (
    "knowledge_repo_overview",
    "knowledge_search",
    "knowledge_get_object",
    "knowledge_get_related",
    "knowledge_get_evidence",
    "knowledge_context_for_task",
    "knowledge_status",
)

_OBJECT_ARGUMENT = {
    "type": "object",
    "properties": {
        "object_id": {"type": "string"},
        "include_stale": {"type": "boolean", "default": False},
    },
    "required": ["object_id"],
}

_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "knowledge_repo_overview": {
        "description": (
            "Read the verified knowledge overview: generation stamps, "
            "object counts by type, and attributed human overlays."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    "knowledge_search": {
        "description": "Search verified knowledge objects by text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    "knowledge_get_object": {
        "description": (
            "Read one canonical knowledge object; include_stale is a "
            "visibly marked diagnostic mode."
        ),
        "inputSchema": _OBJECT_ARGUMENT,
    },
    "knowledge_get_related": {
        "description": "Read the one-hop relations of a knowledge object.",
        "inputSchema": {
            "type": "object",
            "properties": {"object_id": {"type": "string"}},
            "required": ["object_id"],
        },
    },
    "knowledge_get_evidence": {
        "description": (
            "Read recorded evidence items by known Evidence IDs; access "
            "never leaves the resolved repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["evidence_ids"],
        },
    },
    "knowledge_context_for_task": {
        "description": (
            "Compile budgeted task context from verified knowledge; "
            "include_stale is a visibly marked diagnostic mode."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "budget": {"type": "integer", "default": 6000},
                "include_stale": {"type": "boolean", "default": False},
            },
            "required": ["task"],
        },
    },
    "knowledge_status": {
        "description": (
            "Read the knowledge status: view generations, canonical "
            "objects, and the latest run's target results."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"include_stale": {"type": "boolean"}},
        },
    },
}


class ToolError(RuntimeError):
    """A tool-level failure surfaced as an isError result."""


@dataclass(frozen=True)
class _ToolResult:
    payload: dict[str, Any]
    markdown: str | None = None


def _as_data(value: object) -> str:
    """Human and repository text are data, never markup or instructions."""

    return html.escape(str(value), quote=True)


def serve_mcp(
    repository_root: Path,
    *,
    reader: Any,
    writer: Any,
    snapshot: object | None = None,
) -> None:
    """Serve the seven read-only knowledge tools over stdio JSON-RPC.

    The server never builds, updates, writes canonical state, or
    executes repository code; every handler only reads committed
    artifacts and fails closed unless the verified view is current.
    """

    root = Path(repository_root).resolve()
    for line in reader:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except ValueError:
            _write(
                writer,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "parse error"},
                },
            )
            continue
        if not isinstance(request, dict) or "method" not in request:
            _write(
                writer,
                {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if isinstance(request, dict) else None,
                    "error": {"code": -32600, "message": "invalid request"},
                },
            )
            continue
        if "id" not in request:
            continue  # notification
        response = _dispatch(request, root, snapshot)
        if response is not None:
            _write(writer, response)


def _write(writer: Any, payload: dict[str, Any]) -> None:
    writer.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    writer.write("\n")
    writer.flush()


def _dispatch(
    request: dict[str, Any], root: Path, snapshot: object | None
) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method in ("ping",):
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {"name": name, **_TOOL_SCHEMAS[name]}
                    for name in TOOL_NAMES
                ]
            },
        }
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOL_NAMES:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"unknown tool: {name}"},
            }
        try:
            result = _call_tool(str(name), dict(arguments), root, snapshot)
        except ToolError as error:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": str(error)}],
                    "isError": True,
                },
            }
        content = [
            {
                "type": "text",
                "text": json.dumps(
                    result.payload, ensure_ascii=False, sort_keys=True
                ),
            }
        ]
        if result.markdown is not None:
            content.append({"type": "text", "text": result.markdown})
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": content},
        }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"unknown method: {method}"},
    }


def _call_tool(
    name: str, arguments: dict[str, Any], root: Path, snapshot: object | None
) -> _ToolResult:
    if name == "knowledge_repo_overview":
        return _overview(root, snapshot)
    if name == "knowledge_search":
        return _search(root, arguments, snapshot)
    if name == "knowledge_get_object":
        return _get_object(root, arguments, snapshot)
    if name == "knowledge_get_related":
        return _get_related(root, arguments, snapshot)
    if name == "knowledge_get_evidence":
        return _get_evidence(root, arguments, snapshot)
    if name == "knowledge_context_for_task":
        return _context_for_task(root, arguments)
    if name == "knowledge_status":
        return _status(root, arguments)
    raise ToolError(f"unknown tool: {name}")


def _gate(root: Path, snapshot: object | None) -> None:
    from knowledge_compiler.retrieval.context import (
        ContextRetrievalError,
        require_current_view,
    )

    try:
        require_current_view(root, snapshot)
    except ContextRetrievalError as error:
        raise ToolError(str(error)) from error


def _load(root: Path) -> tuple[dict[str, object], dict[str, object], dict, dict]:
    from knowledge_compiler.compiler.wiki import _load_compile_inputs
    from knowledge_compiler.human.overlays import load_active_overlays

    objects, packs = _load_compile_inputs(root)
    overlays = load_active_overlays(root)
    manifest = yaml.safe_load((root / ".knowledge/manifest.yaml").read_bytes())
    return objects, packs, overlays, manifest


def _verified(objects: dict[str, object]) -> dict[str, object]:
    return {
        object_id: canonical
        for object_id, canonical in objects.items()
        if canonical.validity.status == "verified"
    }


def _overview(root: Path, snapshot: object | None) -> _ToolResult:
    _gate(root, snapshot)
    objects, _packs, overlays, manifest = _load(root)
    verified = _verified(objects)
    counts: dict[str, int] = {}
    for canonical in verified.values():
        counts[canonical.type] = counts.get(canonical.type, 0) + 1
    payload = {
        "active_generation": manifest.get("active_generation"),
        "agent_views_generation": manifest.get("agent_views_generation"),
        "wiki_generation": manifest.get("wiki_generation"),
        "counts": dict(sorted(counts.items())),
        "objects": [
            {
                "object_id": object_id,
                "type": canonical.type,
                "title": _as_data(canonical.title),
            }
            for object_id, canonical in sorted(verified.items())
        ],
        "human_overlays": [
            {
                "object_id": object_id,
                "source": "human",
                "updated_at": overlay.updated_at.isoformat(),
                "sections": len(overlay.sections),
                "notes": len(overlay.notes),
            }
            for object_id, overlay in sorted(overlays.items())
        ],
    }
    return _ToolResult(payload)


def _search(
    root: Path, arguments: dict[str, Any], snapshot: object | None
) -> _ToolResult:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolError("query must be a non-empty string")
    limit = arguments.get("limit", 10)
    if not isinstance(limit, int) or limit < 1 or limit > 50:
        raise ToolError("limit must be an integer between 1 and 50")
    _gate(root, snapshot)
    from knowledge_compiler.retrieval import store

    objects, _packs, _overlays, _manifest = _load(root)
    verified = _verified(objects)
    try:
        ranks = store.match_objects(root / ".knowledge/cache/knowledge-index.sqlite3", query)
    except store.IndexStoreError as error:
        raise ToolError(f"knowledge_update_required: {error}") from error
    ordered = sorted(
        (object_id for object_id in ranks if object_id in verified),
        key=lambda object_id: ranks[object_id],
    )[:limit]
    return _ToolResult(
        {
            "results": [
                {
                    "object_id": object_id,
                    "type": verified[object_id].type,
                    "title": _as_data(verified[object_id].title),
                    "summary": _as_data(verified[object_id].summary.text),
                }
                for object_id in ordered
            ]
        }
    )


def _get_object(
    root: Path, arguments: dict[str, Any], snapshot: object | None
) -> _ToolResult:
    object_id = arguments.get("object_id")
    if not isinstance(object_id, str) or not object_id.strip():
        raise ToolError("object_id must be a non-empty string")
    include_stale = bool(arguments.get("include_stale", False))
    objects, _packs, overlays, _manifest = _load(root)
    if not include_stale:
        _gate(root, snapshot)
        objects = _verified(objects)
    canonical = objects.get(object_id)
    if canonical is None:
        raise ToolError(
            "object is not part of the current verified view: "
            + _as_data(object_id)
        )
    overlay = overlays.get(object_id)
    payload: dict[str, Any] = {
        "object_id": object_id,
        "type": canonical.type,
        "title": _as_data(canonical.title),
        "summary": _as_data(canonical.summary.text),
        "claims": [
            {
                "id": claim.id,
                "statement": _as_data(claim.statement),
                "evidence_ids": list(claim.evidence_ids),
            }
            for claim in canonical.claims
        ],
        "validity": canonical.validity.status,
        "verified_commit": canonical.validity.verified_commit,
        "human_sections": [],
        "human_notes": [],
    }
    if canonical.validity.status == "stale":
        payload["stale_reason"] = _as_data(
            canonical.validity.stale_reason or "unknown"
        )
    if include_stale:
        payload["diagnostic"] = True
    if overlay is not None:
        payload["human_sections"] = [
            {
                "field": section.field,
                "mode": section.mode,
                "source": "human",
                "text": _as_data(section.text),
            }
            for section in overlay.sections
        ]
        payload["human_notes"] = [
            {
                "id": note.id,
                "source": "human",
                "text": _as_data(note.text),
            }
            for note in overlay.notes
        ]
    return _ToolResult(payload)


def _get_related(
    root: Path, arguments: dict[str, Any], snapshot: object | None
) -> _ToolResult:
    object_id = arguments.get("object_id")
    if not isinstance(object_id, str) or not object_id.strip():
        raise ToolError("object_id must be a non-empty string")
    _gate(root, snapshot)
    objects, _packs, _overlays, _manifest = _load(root)
    verified = _verified(objects)
    canonical = verified.get(object_id)
    if canonical is None:
        raise ToolError(
            "object is not part of the current verified view: "
            + _as_data(object_id)
        )
    forward = _relations_of(canonical)
    inbound = [
        (other.id, predicate)
        for other in verified.values()
        if other.id != object_id
        for _source, target, predicate in _relations_of(other)
        if target == object_id
    ]
    return _ToolResult(
        {
            "object_id": object_id,
            "relations": [
                {"predicate": _as_data(predicate), "target": target}
                for _source, target, predicate in forward
            ],
            "inbound": [
                {"object_id": source, "predicate": _as_data(predicate)}
                for source, predicate in sorted(set(inbound))
            ],
        }
    )


def _get_evidence(
    root: Path, arguments: dict[str, Any], snapshot: object | None
) -> _ToolResult:
    evidence_ids = arguments.get("evidence_ids")
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or not all(isinstance(item, str) for item in evidence_ids)
    ):
        raise ToolError("evidence_ids must be a non-empty list of strings")
    _gate(root, snapshot)
    _objects, packs, _overlays, _manifest = _load(root)
    known = {
        item.id: item
        for pack in packs.values()
        for item in pack.evidence
    }
    found = []
    for evidence_id in evidence_ids:
        item = known.get(evidence_id)
        if item is None:
            continue
        found.append(
            {
                "evidence_id": item.id,
                "path": item.path,
                "symbol": item.symbol,
                "start_line": item.start_line,
                "end_line": item.end_line,
                "commit": item.commit,
                "excerpt": _as_data(item.excerpt),
            }
        )
    return _ToolResult(
        {
            "evidence": found,
            "unknown_evidence_ids": [
                evidence_id
                for evidence_id in evidence_ids
                if evidence_id not in known
            ],
        }
    )


def _context_for_task(
    root: Path, arguments: dict[str, Any]
) -> _ToolResult:
    task = arguments.get("task")
    if not isinstance(task, str) or not task.strip():
        raise ToolError("task must be a non-empty string")
    budget = arguments.get("budget", 6000)
    if not isinstance(budget, int) or budget < 100 or budget > 100000:
        raise ToolError("budget must be an integer between 100 and 100000")
    from knowledge_compiler.retrieval.context import (
        ContextRetrievalError,
        retrieve_task_context,
    )

    try:
        markdown = retrieve_task_context(
            root,
            task,
            budget=budget,
            include_stale=bool(arguments.get("include_stale", False)),
        )
    except ContextRetrievalError as error:
        raise ToolError(str(error)) from error
    return _ToolResult({"task": task}, markdown=markdown)


def _status(root: Path, arguments: dict[str, Any]) -> _ToolResult:
    include_stale = bool(arguments.get("include_stale", False))
    # Status reports committed state the same way the CLI does; it never
    # serves verified agent views, so the freshness gate does not apply
    # and the diagnostic flag only marks the response.
    payload: dict[str, Any] = {}
    if include_stale:
        payload["diagnostic"] = True
    manifest_path = root / ".knowledge/manifest.yaml"
    if manifest_path.is_file():
        manifest = yaml.safe_load(manifest_path.read_bytes())
        payload["view_generations"] = {
            key: manifest.get(key)
            for key in (
                "active_generation",
                "agent_views_generation",
                "wiki_generation",
            )
        }
    else:
        payload["view_generations"] = {"error": "no committed generation"}
    try:
        objects, _packs, _overlays, _manifest = _load(root)
    except Exception as error:
        raise ToolError(f"knowledge state is unreadable: {error}") from error
    payload["canonical_objects"] = [
        {
            "object_id": object_id,
            "type": canonical.type,
            "validity": canonical.validity.status,
        }
        for object_id, canonical in sorted(objects.items())
    ]
    runs_root = root / ".knowledge/state/runs"
    if runs_root.is_dir():
        from knowledge_compiler.orchestrator.store import RunStore

        records = RunStore(runs_root)._list_runs()
        record = next(
            (item for item in records if item.active),
            records[-1] if records else None,
        )
        if record is not None:
            payload["run_id"] = record.run_id
            payload["target_results"] = [
                {
                    "target_id": target.target_id,
                    "state": target.state.value,
                    "result": (
                        target.result.value if target.result else None
                    ),
                    "published_object_id": target.published_object_id,
                }
                for target in sorted(
                    record.targets, key=lambda item: item.target_id
                )
            ]
    return _ToolResult(payload)


def _relations_of(canonical: object) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for field, default in (
        ("dependencies", "depends on"),
        ("relations", "relates to"),
    ):
        for item in getattr(canonical, field, ()) or ():
            target = getattr(item, "target", None)
            if isinstance(target, str):
                predicate = getattr(item, "predicate", None) or default
                rows.append((canonical.id, target, predicate))
    for target in getattr(canonical, "related_objects", ()) or ():
        if isinstance(target, str):
            rows.append((canonical.id, target, "related to"))
    for relationship in getattr(canonical, "relationships", ()) or ():
        target = getattr(relationship, "target", None)
        predicate = getattr(relationship, "predicate", "relates to")
        if isinstance(target, str):
            rows.append((canonical.id, target, predicate))
    return sorted(set(rows))


def main() -> None:
    import sys

    serve_mcp(Path(sys.argv[1] if len(sys.argv) > 1 else "."), reader=sys.stdin, writer=sys.stdout)


__all__ = ["PROTOCOL_VERSION", "SERVER_NAME", "SERVER_VERSION", "TOOL_NAMES", "serve_mcp"]
