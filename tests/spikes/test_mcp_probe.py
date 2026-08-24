from pathlib import Path
from types import SimpleNamespace

import pytest

from knowledge_compiler.spikes.fixture_repo import ProbeRepository
from knowledge_compiler.spikes.mcp_probe import probe_session, select_tools


def test_select_tools_matches_public_capabilities() -> None:
    tools = [
        "codewiki_graph_search",
        "codewiki_graph_explore",
        "codewiki_graph_affected",
        "codewiki_files",
    ]

    selected = select_tools(tools, {"symbols", "topic_exploration", "affected"})

    assert selected == {
        "affected": "codewiki_graph_affected",
        "symbols": "codewiki_graph_search",
        "topic_exploration": "codewiki_graph_explore",
    }


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self) -> SimpleNamespace:
        return SimpleNamespace(tools=[
            SimpleNamespace(
                name="codewiki_graph_search",
                inputSchema={"type": "object", "properties": {"query": {}, "limit": {}}},
            ),
            SimpleNamespace(
                name="codewiki_graph_affected",
                inputSchema={"type": "object", "properties": {"files": {}}},
            ),
        ])

    async def call_tool(self, name: str, arguments: dict[str, object]) -> SimpleNamespace:
        self.calls.append((name, arguments))
        return SimpleNamespace(
            isError=False,
            structuredContent={"result": ["CheckoutService.checkout"]},
            content=[SimpleNamespace(type="text", text="bounded result")],
        )


@pytest.mark.anyio
async def test_probe_session_calls_only_required_bounded_tools() -> None:
    session = FakeSession()
    repo = ProbeRepository(Path("/tmp/probe"), "abc123", ())

    observations = await probe_session(session, repo, {"symbols", "affected"})

    assert {item.name for item in observations} == {"symbols", "affected"}
    assert {name for name, _ in session.calls} == {
        "codewiki_graph_search",
        "codewiki_graph_affected",
    }
    search_arguments = next(args for name, args in session.calls if name == "codewiki_graph_search")
    assert search_arguments["limit"] <= 10
