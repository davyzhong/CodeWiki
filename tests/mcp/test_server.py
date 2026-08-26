from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests/fixtures/probe_repo"
sys.path.insert(0, str(ROOT / "tests/integration"))
sys.path.insert(0, str(ROOT / "tests/storage"))

from test_generation_publication import _verified_inputs  # noqa: E402
from test_typed_publication import canonicalize  # noqa: E402

from knowledge_compiler.mcp_server import TOOL_NAMES, serve_mcp  # noqa: E402


class Client:
    def __init__(self, root: Path) -> None:
        self.reader = io.StringIO()
        self.writer = io.StringIO()
        self.root = root
        self._id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        request = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            request["params"] = params
        self.reader = io.StringIO(json.dumps(request) + "\n")
        serve_mcp(self.root, reader=self.reader, writer=self.writer)
        lines = [
            line
            for line in self.writer.getvalue().splitlines()
            if line.strip()
        ]
        return json.loads(lines[-1])

    def tool(self, name: str, arguments: dict | None = None) -> dict:
        response = self.call(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        if "error" in response:
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(response["error"]),
                    }
                ],
            }
        return response["result"]

    @staticmethod
    def payload(result: dict) -> dict:
        assert result.get("isError") is not True, result
        block = result["content"][0]
        assert block["type"] == "text"
        return json.loads(block["text"])


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(PROBE, repo)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@e.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "T"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True
    )
    return repo


def compiled_world(repo: Path) -> dict[str, str]:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki
    from knowledge_compiler.retrieval.context import build_knowledge_index
    from knowledge_compiler.storage import GenerationPublisher

    module, pack = _verified_inputs()
    ids = {"module": module.id}
    items: list[tuple[object, object | None]] = [(module, pack)]
    for type_name in ("architecture", "flow", "rule", "tech-stack"):
        canonical = canonicalize(type_name).canonical
        assert canonical is not None
        ids[type_name] = canonical.id
        items.append((canonical, None))
    target = repo / ".knowledge/state/runs/manual-mcp/targets" / module.id
    target.mkdir(parents=True)
    (target / "verified.json").write_text(
        json.dumps(
            {
                "canonical": module.model_dump(mode="json"),
                "evidence_pack": pack.model_dump(mode="json"),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    overlay = repo / ".knowledge/human/modules" / f"{module.id}.yaml"
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {module.id}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections: []\n"
        "notes:\n"
        f"  - id: {module.id}.note.ops\n"
        "    text: Human <b>note</b> with markup.\n"
        "    basis: incident review\n",
        encoding="utf-8",
    )
    GenerationPublisher(repo).publish_generation("gen-mcp-001", tuple(items))
    compile_repository_wiki(repo)
    build_knowledge_index(repo)
    return ids


def test_initialize_and_tools_list_expose_exactly_seven_read_only_tools(
    tmp_path: Path,
) -> None:
    client = Client(make_repo(tmp_path))

    initialized = client.call(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    )
    server_info = initialized["result"]
    assert "tools" in server_info["capabilities"]

    listed = client.call("tools/list")
    names = tuple(tool["name"] for tool in listed["result"]["tools"])
    assert names == TOOL_NAMES
    assert len(names) == 7
    for tool in listed["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"


def test_default_reads_fail_closed_without_a_current_verified_index(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    client = Client(repo)
    from knowledge_compiler.storage import GenerationPublisher

    module, pack = _verified_inputs()
    GenerationPublisher(repo).publish_generation(
        "gen-mcp-closed", ((module, pack),)
    )

    for name, arguments in (
        ("knowledge_repo_overview", {}),
        ("knowledge_search", {"query": "checkout"}),
        ("knowledge_get_object", {"object_id": module.id}),
        ("knowledge_get_related", {"object_id": module.id}),
        ("knowledge_get_evidence", {"evidence_ids": ["ev.any.01"]}),
        ("knowledge_context_for_task", {"task": "checkout"}),
    ):
        result = client.tool(name, arguments)
        assert result["isError"] is True, (name, result)
        assert "knowledge_update_required" in result["content"][0]["text"]


def test_tools_serve_compiled_knowledge_with_human_attribution(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    ids = compiled_world(repo)
    client = Client(repo)

    overview = Client.payload(client.tool("knowledge_repo_overview"))
    assert overview["active_generation"] == "gen-mcp-001"
    assert overview["counts"]["module"] == 1
    human = overview["human_overlays"][0]
    assert human["object_id"] == ids["module"]
    assert human["source"] == "human"

    search = Client.payload(
        client.tool("knowledge_search", {"query": "checkout"})
    )
    assert ids["module"] in [item["object_id"] for item in search["results"]]

    obj = Client.payload(
        client.tool("knowledge_get_object", {"object_id": ids["module"]})
    )
    assert obj["object_id"] == ids["module"]
    assert obj["validity"] == "verified"
    assert obj["claims"]
    assert obj["human_notes"][0]["source"] == "human"
    assert "<b>" not in json.dumps(obj["human_notes"][0]["text"])

    related = Client.payload(
        client.tool("knowledge_get_related", {"object_id": ids["module"]})
    )
    assert "relations" in related

    context = client.tool(
        "knowledge_context_for_task", {"task": "inventory reservation"}
    )
    assert "Task context" in context["content"][1]["text"]

    evidence = Client.payload(
        client.tool(
            "knowledge_get_evidence", {"evidence_ids": ["missing-id"]}
        )
    )
    assert evidence["unknown_evidence_ids"] == ["missing-id"]


def test_status_and_stale_diagnostics_are_marked(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    ids = compiled_world(repo)
    client = Client(repo)

    status = Client.payload(client.tool("knowledge_status"))
    assert status["view_generations"]["active_generation"] == "gen-mcp-001"

    from knowledge_compiler.contracts.knowledge import ModuleKnowledge
    from knowledge_compiler.storage import GenerationPublisher

    module, pack = _verified_inputs()
    data = module.model_dump(mode="json")
    data["validity"] = {
        "status": "stale",
        "verified_commit": module.validity.verified_commit,
        "stale_reason": "evidence changed",
    }
    GenerationPublisher(repo).publish_generation(
        "gen-mcp-stale", ((ModuleKnowledge.model_validate(data), pack),)
    )

    fresh = client.tool("knowledge_get_object", {"object_id": ids["module"]})
    assert fresh["isError"] is True

    diagnostic = Client.payload(
        client.tool(
            "knowledge_get_object",
            {"object_id": ids["module"], "include_stale": True},
        )
    )
    assert diagnostic["diagnostic"] is True
    assert diagnostic["validity"] == "stale"
    assert diagnostic["stale_reason"] == "evidence changed"


def test_unknown_tool_and_malformed_calls_are_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    compiled_world(repo)
    client = Client(repo)

    unknown = client.tool("knowledge_build", {})
    assert "error" in unknown or unknown.get("isError") is True

    client.reader = io.StringIO("{not json\n")
    client.writer = io.StringIO()
    serve_mcp(repo, reader=client.reader, writer=client.writer)
    response = json.loads(client.writer.getvalue().splitlines()[-1])
    assert response["error"]["code"] == -32700


def test_tool_calls_never_mutate_the_knowledge_tree(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    compiled_world(repo)
    client = Client(repo)

    def snapshot() -> dict[str, bytes]:
        return {
            str(path.relative_to(repo)): path.read_bytes()
            for path in sorted(repo.rglob("*"))
            if path.is_file()
        }

    before = snapshot()
    for name, arguments in (
        ("knowledge_repo_overview", {}),
        ("knowledge_search", {"query": "inventory"}),
        ("knowledge_get_object", {"object_id": "module.shop.checkout"}),
        ("knowledge_get_related", {"object_id": "module.shop.checkout"}),
        (
            "knowledge_get_evidence",
            {"evidence_ids": ["ev.shop.checkout.01"]},
        ),
        ("knowledge_context_for_task", {"task": "inventory"}),
        ("knowledge_status", {}),
    ):
        client.tool(name, arguments)
    assert snapshot() == before


def test_argument_bounds_are_enforced(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    compiled_world(repo)
    client = Client(repo)

    for name, arguments in (
        ("knowledge_search", {"query": "x", "limit": 0}),
        ("knowledge_search", {"query": "x", "limit": 51}),
        ("knowledge_search", {"query": "   "}),
        ("knowledge_get_object", {"object_id": ""}),
        ("knowledge_context_for_task", {"task": "x", "budget": 1}),
        ("knowledge_context_for_task", {"task": "x", "budget": 10_000_000}),
        ("knowledge_get_evidence", {"evidence_ids": []}),
        ("knowledge_get_related", {"object_id": "../../etc"}),
    ):
        result = client.tool(name, arguments)
        assert result["isError"] is True, (name, arguments, result)


def test_notifications_produce_no_response(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    writer = io.StringIO()
    serve_mcp(
        repo,
        reader=io.StringIO(
            json.dumps(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}
            )
            + "\n"
        ),
        writer=writer,
    )
    assert writer.getvalue() == ""
