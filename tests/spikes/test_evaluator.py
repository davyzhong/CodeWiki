from copy import deepcopy
import json
from pathlib import Path

from knowledge_compiler.spikes.evaluator import evaluate
from knowledge_compiler.spikes.main import render_report
from knowledge_compiler.spikes.observations import ProbeBundle


def complete_bundle_dict() -> dict:
    def command(name: str, value: object) -> dict:
        return {
            "name": name,
            "argv": [name],
            "returncode": 0,
            "stdout": "structured output",
            "stderr": "",
            "json_value": value,
        }

    return {
        "schema_version": "0.1",
        "codewiki_version": "codewiki 0.6.5",
        "repository_commit": "abc123",
        "commands": [
            command("version", None),
            command("repos_add", {"repository": {"id": "probe-repo", "path": "<REPO>"}}),
            command("analyze", {"status": "completed", "repository_id": "probe-repo"}),
            command("repos_scan", {"files": [
                {"path": "src/shop/checkout.py", "language": "python"},
                {"path": "src/shop/inventory.py", "language": "python"},
            ]}),
            command("graph_search", {"nodes": [
                {
                    "name": "CheckoutService.checkout",
                    "path": "src/shop/checkout.py",
                    "start_line": 8,
                    "end_line": 11,
                },
                {
                    "name": "Inventory.reserve",
                    "path": "src/shop/inventory.py",
                    "start_line": 2,
                    "end_line": 3,
                },
            ]}),
            command("graph_explore", {
                "nodes": ["CheckoutService.checkout", "Inventory.reserve"],
                "edges": [
                    {
                        "source": "shop.checkout",
                        "predicate": "imports",
                        "target": "shop.inventory",
                    },
                    {
                        "source": "CheckoutService.checkout",
                        "predicate": "calls",
                        "target": "Inventory.reserve",
                    },
                ],
                "sources": [{
                    "path": "src/shop/checkout.py",
                    "start_line": 8,
                    "end_line": 11,
                }],
            }),
            command("graph_affected", {"affected": ["CheckoutService.checkout"]}),
            command("update", {"status": "completed"}),
            command("graph_search_after_update", {"nodes": ["CheckoutService.checkout"]}),
        ],
        "mcp": [],
    }


def test_evaluate_returns_no_go_when_calls_are_missing() -> None:
    data = deepcopy(complete_bundle_dict())
    explore = next(item for item in data["commands"] if item["name"] == "graph_explore")
    explore["json_value"]["edges"] = [explore["json_value"]["edges"][0]]

    decision = evaluate(ProbeBundle.model_validate(data))

    assert decision.decision == "no_go"
    assert "calls" in decision.missing_capabilities


def test_evaluate_returns_go_for_complete_public_contract() -> None:
    decision = evaluate(ProbeBundle.model_validate(complete_bundle_dict()))

    assert decision.decision == "go"
    assert decision.missing_capabilities == []
    assert all(item.evidence for item in decision.capabilities)


def test_render_report_contains_required_sections() -> None:
    bundle = ProbeBundle.model_validate(complete_bundle_dict())
    decision = evaluate(bundle)

    report = render_report(bundle, decision)

    assert "# CodeWiki Public-Surface Spike" in report
    assert "Decision: `go`" in report
    assert "## CLI observations" in report
    assert "## MCP fallback observations" in report
    assert "## Capability matrix" in report
    assert "## Missing or ambiguous capabilities" in report
    assert "## Adapter recommendation" in report


def test_evaluate_accepts_codewiki_065_public_shapes() -> None:
    data = complete_bundle_dict()
    data["commands"].append({
        "name": "package_version",
        "argv": ["python", "-c", "metadata"],
        "returncode": 0,
        "stdout": "codewiki 0.6.5\n",
        "stderr": "",
        "json_value": None,
    })
    analyze = next(item for item in data["commands"] if item["name"] == "analyze")
    analyze["json_value"]["status"] = "done"
    update = next(item for item in data["commands"] if item["name"] == "update")
    update["json_value"]["status"] = "done"
    explore = next(item for item in data["commands"] if item["name"] == "graph_explore")
    explore["json_value"] = {
        "entry_points": [
            {
                "name": "checkout",
                "symbol_id": "src/shop/checkout.py::CheckoutService.checkout",
                "file_path": "src/shop/checkout.py",
                "start_line": 8,
                "end_line": 11,
            },
            {
                "name": "reserve",
                "symbol_id": "src/shop/inventory.py::Inventory.reserve",
                "file_path": "src/shop/inventory.py",
                "start_line": 2,
                "end_line": 3,
            },
        ],
        "relationships": [{
            "source": "CheckoutService.checkout",
            "type": "calls",
            "target": "Inventory.reserve",
        }],
        "source_sections": [{
            "file_path": "src/shop/checkout.py",
            "start_line": 1,
            "end_line": 11,
            "content": "from shop.inventory import Inventory",
        }],
        "query": "checkout inventory",
    }

    decision = evaluate(ProbeBundle.model_validate(data))

    assert decision.decision == "go"


def test_captured_codewiki_065_contract_reproduces_go_decision() -> None:
    fixture = Path("tests/fixtures/codewiki/0.6/cli-observations.json")
    bundle = ProbeBundle.model_validate(json.loads(fixture.read_text(encoding="utf-8")))

    decision = evaluate(bundle)

    assert decision.decision == "go"
