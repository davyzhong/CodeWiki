from __future__ import annotations

from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowledge_compiler.spikes.fixture_repo import ProbeRepository
from knowledge_compiler.spikes.observations import McpObservation, sanitize_text


TOOL_CANDIDATES = {
    "survey": ("codewiki_files", "codewiki_indexed_files"),
    "symbols": ("codewiki_graph_search", "codewiki_search"),
    "topic_exploration": ("codewiki_graph_explore", "codewiki_context"),
    "affected": ("codewiki_graph_affected", "codewiki_affected"),
    "source_references": ("codewiki_node", "codewiki_graph_search"),
}

ARGUMENTS: dict[str, dict[str, Any]] = {
    "survey": {"path": "{repo}"},
    "symbols": {"query": "CheckoutService", "limit": 10},
    "topic_exploration": {"query": "checkout inventory", "max_hops": 2},
    "affected": {"files": ["src/shop/inventory.py"]},
    "source_references": {"query": "Inventory.reserve", "limit": 10},
}


def select_tools(available: list[str], required: set[str]) -> dict[str, str]:
    available_set = set(available)
    return {
        capability: next(name for name in TOOL_CANDIDATES[capability] if name in available_set)
        for capability in sorted(required & TOOL_CANDIDATES.keys())
        if any(name in available_set for name in TOOL_CANDIDATES[capability])
    }


def _sanitize_value(value: Any, repo_root: Path) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, repo_root)
    if isinstance(value, list):
        return [_sanitize_value(item, repo_root) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_value(item, repo_root) for key, item in value.items()}
    return value


def _tool_schema(tool: Any) -> dict[str, Any]:
    return getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}


async def probe_session(
    session: Any,
    repo: ProbeRepository,
    required: set[str],
) -> list[McpObservation]:
    listed = await session.list_tools()
    tools = list(listed.tools)
    by_name = {tool.name: tool for tool in tools}
    selected = select_tools(list(by_name), required)
    observations: list[McpObservation] = []

    for capability, tool_name in selected.items():
        arguments = {
            key: (str(repo.root) if value == "{repo}" else value)
            for key, value in ARGUMENTS[capability].items()
        }
        try:
            result = await session.call_tool(tool_name, arguments)
        except Exception:
            properties = _tool_schema(by_name[tool_name]).get("properties", {})
            retry_arguments = {key: value for key, value in arguments.items() if key in properties}
            try:
                result = await session.call_tool(tool_name, retry_arguments)
                arguments = retry_arguments
            except Exception as exc:
                observations.append(
                    McpObservation(
                        name=capability,
                        tool_name=tool_name,
                        arguments=_sanitize_value(retry_arguments, repo.root),
                        is_error=True,
                        text_content=[sanitize_text(str(exc), repo.root)],
                    )
                )
                continue

        text_content = [
            sanitize_text(item.text, repo.root)
            for item in getattr(result, "content", [])
            if getattr(item, "type", None) == "text"
        ]
        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        observations.append(
            McpObservation(
                name=capability,
                tool_name=tool_name,
                arguments=_sanitize_value(arguments, repo.root),
                is_error=bool(getattr(result, "isError", getattr(result, "is_error", False))),
                structured_content=_sanitize_value(structured, repo.root),
                text_content=text_content,
            )
        )
    return observations


async def _run_mcp_probe(
    executable: str,
    repo: ProbeRepository,
    required: set[str],
) -> list[McpObservation]:
    command = str(Path(executable).resolve()) if "/" in executable else executable
    parameters = StdioServerParameters(
        command=command,
        args=["mcp", "--lite", "--path", str(repo.root)],
    )
    try:
        with anyio.fail_after(120):
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    return await probe_session(session, repo, required)
    except Exception as exc:
        return [
            McpObservation(
                name="mcp_transport",
                tool_name="",
                arguments={},
                is_error=True,
                text_content=[sanitize_text(str(exc), repo.root)],
            )
        ]


def run_mcp_probe(
    executable: str,
    repo: ProbeRepository,
    required: set[str],
) -> list[McpObservation]:
    return anyio.run(_run_mcp_probe, executable, repo, required)
