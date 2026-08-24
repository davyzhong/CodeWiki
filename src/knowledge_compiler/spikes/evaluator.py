from __future__ import annotations

import json
import re
from typing import Any, Callable, Literal

from pydantic import BaseModel

from knowledge_compiler.spikes.observations import ProbeBundle


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


class CapabilityResult(BaseModel):
    capability: str
    status: Literal["supported", "missing", "ambiguous"]
    evidence: list[str]


class SpikeDecision(BaseModel):
    decision: Literal["go", "no_go"]
    capabilities: list[CapabilityResult]
    missing_capabilities: list[str]


def _command(bundle: ProbeBundle, name: str) -> Any | None:
    return next((item for item in bundle.commands if item.name == name), None)


def _all_values(bundle: ProbeBundle) -> list[tuple[str, Any]]:
    values = [
        (f"cli:{item.name}", item.json_value)
        for item in bundle.commands
        if item.returncode == 0 and item.json_value is not None
    ]
    values.extend(
        (f"mcp:{item.name}:{item.tool_name}", item.structured_content)
        for item in bundle.mcp
        if not item.is_error and item.structured_content is not None
    )
    return values


def _text(value: Any) -> str:
    return json.dumps(value, sort_keys=True).lower()


def _find_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        found = [value]
        for child in value.values():
            found.extend(_find_dicts(child))
        return found
    if isinstance(value, list):
        found: list[dict[str, Any]] = []
        for child in value:
            found.extend(_find_dicts(child))
        return found
    return []


def _supported(capability: str, evidence: list[str]) -> CapabilityResult:
    return CapabilityResult(
        capability=capability,
        status="supported" if evidence else "missing",
        evidence=evidence or ["no public-surface evidence"],
    )


def _version(bundle: ProbeBundle) -> CapabilityResult:
    evidence = []
    if bundle.codewiki_version and re.search(r"(?<!\d)0\.6(?:\.\d+)?(?!\d)", bundle.codewiki_version):
        evidence.append("bundle:codewiki_version")
    return _supported("version", evidence)


def _registration(bundle: ProbeBundle) -> CapabilityResult:
    item = _command(bundle, "repos_add")
    evidence = []
    if item and item.returncode == 0 and any(
        key in dictionary
        for dictionary in _find_dicts(item.json_value)
        for key in ("id", "repository_id", "path")
    ):
        evidence.append("cli:repos_add")
    return _supported("repository_registration", evidence)


def _successful_status(bundle: ProbeBundle, name: str, capability: str) -> CapabilityResult:
    item = _command(bundle, name)
    evidence = []
    if item and item.returncode == 0:
        text = _text(item.json_value)
        if any(status in text for status in ("completed", "success", "succeeded", "indexed", "done")):
            evidence.append(f"cli:{name}")
    return _supported(capability, evidence)


def _survey(bundle: ProbeBundle) -> CapabilityResult:
    evidence = [
        source
        for source, value in _all_values(bundle)
        if "src/shop/checkout.py" in _text(value) and "python" in _text(value)
    ]
    return _supported("repository_survey", evidence)


def _symbols(bundle: ProbeBundle) -> CapabilityResult:
    evidence = []
    for source, value in _all_values(bundle):
        text = _text(value)
        if "checkoutservice" in text and "inventory.reserve" in text:
            evidence.append(source)
    return _supported("symbols", evidence)


def _edge(bundle: ProbeBundle, capability: str, predicates: tuple[str, ...]) -> CapabilityResult:
    evidence = []
    for source, value in _all_values(bundle):
        for dictionary in _find_dicts(value):
            predicate = str(dictionary.get("predicate", dictionary.get("type", ""))).lower()
            if predicate in predicates and dictionary.get("source") and dictionary.get("target"):
                evidence.append(source)
                break
    return _supported(capability, sorted(set(evidence)))


def _source_references(bundle: ProbeBundle) -> CapabilityResult:
    evidence = []
    for source, value in _all_values(bundle):
        if any(
            isinstance(item.get("path", item.get("file_path")), str)
            and isinstance(item.get("start_line"), int)
            and isinstance(item.get("end_line"), int)
            for item in _find_dicts(value)
        ):
            evidence.append(source)
    return _supported("source_references", evidence)


def _imports(bundle: ProbeBundle) -> CapabilityResult:
    result = _edge(bundle, "imports", ("import", "imports"))
    if result.status == "supported":
        return result
    evidence = [
        source
        for source, value in _all_values(bundle)
        if re.search(r"\b(from\s+shop\.\w+\s+import|import\s+shop\.)", _text(value))
    ]
    return _supported("imports", evidence)


def _named_content(bundle: ProbeBundle, capability: str, names: tuple[str, ...], terms: tuple[str, ...]) -> CapabilityResult:
    evidence = []
    for item in bundle.commands:
        if item.name in names and item.returncode == 0 and all(term in _text(item.json_value) for term in terms):
            evidence.append(f"cli:{item.name}")
    for item in bundle.mcp:
        if item.name == capability and not item.is_error and all(
            term in _text(item.structured_content) for term in terms
        ):
            evidence.append(f"mcp:{item.name}:{item.tool_name}")
    return _supported(capability, evidence)


def _incremental(bundle: ProbeBundle) -> CapabilityResult:
    update = _successful_status(bundle, "update", "incremental_update")
    after = _command(bundle, "graph_search_after_update")
    if update.status == "supported" and after and after.returncode == 0 and after.json_value:
        return _supported("incremental_update", ["cli:update", "cli:graph_search_after_update"])
    return _supported("incremental_update", [])


def _bounded(bundle: ProbeBundle) -> CapabilityResult:
    successful_cli = [
        item
        for item in bundle.commands
        if item.name not in {"version", "package_version"} and item.returncode == 0
    ]
    evidence = []
    if successful_cli and all(item.json_value is not None for item in successful_cli):
        evidence.append("cli:parseable-json")
    if bundle.mcp and all(item.is_error or item.structured_content is not None for item in bundle.mcp):
        evidence.append("mcp:structured-content")
    return _supported("bounded_machine_output", evidence)


def evaluate(bundle: ProbeBundle) -> SpikeDecision:
    checks: list[Callable[[], CapabilityResult]] = [
        lambda: _version(bundle),
        lambda: _registration(bundle),
        lambda: _successful_status(bundle, "analyze", "full_index"),
        lambda: _survey(bundle),
        lambda: _symbols(bundle),
        lambda: _imports(bundle),
        lambda: _edge(bundle, "calls", ("call", "calls")),
        lambda: _source_references(bundle),
        lambda: _named_content(
            bundle,
            "topic_exploration",
            ("graph_explore",),
            ("checkout", "inventory"),
        ),
        lambda: _named_content(
            bundle,
            "affected",
            ("graph_affected",),
            ("checkout",),
        ),
        lambda: _incremental(bundle),
        lambda: _bounded(bundle),
    ]
    results = [check() for check in checks]
    missing = [item.capability for item in results if item.status != "supported"]
    return SpikeDecision(
        decision="go" if not missing else "no_go",
        capabilities=results,
        missing_capabilities=missing,
    )
