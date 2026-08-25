from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from knowledge_compiler.contracts.repository import EvidenceBudget, PlanTarget
from knowledge_compiler.contracts.evidence import (
    EvidenceItem,
    EvidencePack,
    GraphFact,
    RepositorySurvey,
    build_evidence_id,
)
from knowledge_compiler.contracts.repository import RepositorySnapshot
from knowledge_compiler.providers.base import IndexStatus
from knowledge_compiler.providers.codewiki_cli import (
    CodewikiCliError,
    require_supported_version,
)


_CREDENTIAL_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}"
    ),
)


def redact_credentials(text: str) -> tuple[str, bool]:
    redacted = text
    matched = False
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(redacted):
            matched = True
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted, matched


def _relative_member(value: str, root_name: str) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith("<REPO>/"):
        return value[len("<REPO>/"):]
    marker = f"{root_name}/"
    index = value.find(marker)
    candidate = value[index + len(marker):] if index != -1 else value
    parsed = PurePosixPath(candidate)
    if (
        not candidate
        or candidate.startswith("/")
        or ".." in parsed.parts
        or candidate.startswith("<")
    ):
        return None
    return candidate


def normalize_scan(payload: dict[str, Any], root_name: str) -> dict[str, Any]:
    files: list[str] = []
    languages: list[str] = []
    for entry in payload.get("files", []):
        member = _relative_member(entry.get("absolute_path", ""), root_name)
        if member is None:
            continue
        files.append(member)
        language = entry.get("language")
        if entry.get("is_source") and isinstance(language, str) and language not in languages:
            languages.append(language)
    return {
        "files": sorted(files),
        "languages": sorted(languages),
        "repo": payload.get("repo") or {},
    }


def normalize_search(payload: list[dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    for entry in payload or []:
        node = entry.get("node") if isinstance(entry, dict) else None
        name = node.get("name") if isinstance(node, dict) else None
        if isinstance(name, str) and name and name not in symbols:
            symbols.append(name)
    return sorted(symbols)


def normalize_explore(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_points": payload.get("entry_points") or [],
        "relationships": payload.get("relationships") or [],
    }


def normalize_update(payload: dict[str, Any]) -> dict[str, Any]:
    """M5-reserved surface: normalized, never invoked by the M2 harness."""
    return {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "repo_id": payload.get("repo_id"),
        "node_count": payload.get("node_count"),
        "edge_count": payload.get("edge_count"),
        "errors": payload.get("errors") or [],
    }


def normalize_affected(payload: dict[str, Any]) -> dict[str, Any]:
    """M5-reserved surface: normalized, never invoked by the M2 harness."""
    return {
        "repo_id": payload.get("repo_id"),
        "changed_files": payload.get("changed_files") or [],
        "affected_files": payload.get("affected_files") or [],
        "affected_node_ids": payload.get("affected_node_ids") or [],
        "affected_tests": payload.get("affected_tests") or [],
    }


class CodeWikiEvidenceProvider:
    """Adapt the captured public CodeWiki surface into project-owned DTOs."""

    def __init__(self, runner: Any, *, repository_root: Path) -> None:
        require_supported_version(runner.version())
        self._runner = runner
        self._root = Path(repository_root).resolve()

    def _run(self, argv: list[str]) -> Any:
        result = self._runner.run(argv, root=self._root)
        if not result.stdout:
            return None
        try:
            payload = json.loads(result.stdout)
        except ValueError as error:
            raise CodewikiCliError("codewiki output is not valid JSON") from error
        return payload

    def _validate(self, repo: RepositorySnapshot) -> RepositorySnapshot:
        repo = RepositorySnapshot.model_validate(repo)
        if repo.root.resolve() != self._root:
            raise ValueError("repository root mismatch")
        scan = self._run(["codewiki", "repos", "scan", str(self._root), "--json"])
        provider_repo = (scan or {}).get("repo") or {}
        if provider_repo.get("commit_hash") not in (None, repo.commit):
            raise ValueError("provider snapshot commit differs from repository")
        return repo

    def inspect(self, repo: RepositorySnapshot) -> RepositorySurvey:
        validated = self._validate(repo)
        scan = self._run(["codewiki", "repos", "scan", str(self._root), "--json"])
        normalized = normalize_scan(scan or {}, self._root.name)
        search = self._run(
            ["codewiki", "graph", "search", "*", "--repo", str(self._root), "--json"]
        )
        explore = normalize_explore(
            self._run(
                [
                    "codewiki", "graph", "explore", "*", "--repo",
                    str(self._root), "--json",
                ]
            )
            or {}
        )
        communities = self._communities(explore["relationships"])
        return RepositorySurvey(
            repository_id=validated.repository_id,
            snapshot_id=validated.snapshot_id,
            files=tuple(normalized["files"]),
            languages=tuple(normalized["languages"]),
            symbols=tuple(normalize_search(search if isinstance(search, list) else [])),
            graph_communities=communities,
            configuration_facts={"provider": "codewiki"},
        )

    def ensure_index(self, repo: RepositorySnapshot) -> IndexStatus:
        validated = self._validate(repo)
        self._run(["codewiki", "repos", "add", str(self._root), "--json"])
        self._run(["codewiki", "analyze", str(self._root), "--json"])
        return IndexStatus(
            repository_id=validated.repository_id,
            snapshot_id=validated.snapshot_id,
        )

    def build_pack(
        self,
        repo: RepositorySnapshot,
        target: PlanTarget,
        budget: EvidenceBudget,
    ) -> EvidencePack:
        validated = self._validate(repo)
        target = PlanTarget.model_validate(target)
        budget = EvidenceBudget.model_validate(budget)
        explore = normalize_explore(
            self._run(
                [
                    "codewiki", "graph", "explore", target.topic, "--repo",
                    str(self._root), "--json",
                ]
            )
            or {}
        )
        entries = self._select_entries(explore["entry_points"], target)
        evidence: list[EvidenceItem] = []
        for entry in entries:
            item = self._read_evidence(validated, entry)
            if item is not None:
                evidence.append(item)
        graph_facts = self._graph_facts(explore["relationships"], target)
        if len(evidence) > budget.max_items:
            raise ValueError("evidence item budget exceeded")
        model_visible = "".join(item.excerpt for item in evidence)
        if len(model_visible) > budget.max_characters:
            raise ValueError("evidence character budget exceeded")
        token_count = sum(len(item.excerpt.split()) for item in evidence)
        if token_count > budget.max_tokens:
            raise ValueError("evidence token budget exceeded")
        return EvidencePack(
            repository=validated,
            target=target,
            budget=budget,
            evidence=tuple(sorted(evidence, key=lambda item: item.id)),
            graph_facts=tuple(graph_facts),
        )

    def get_evidence(self, repo: RepositorySnapshot, evidence_id: str) -> EvidenceItem:
        pack = self.build_pack(
            repo,
            self._last_target or PlanTarget(id="module.unknown", topic="unknown"),
            EvidenceBudget(max_items=64, max_characters=1_000_000, max_tokens=100_000),
        )
        for item in pack.evidence:
            if item.id == evidence_id:
                return item
        raise KeyError(f"unknown Evidence ID: {evidence_id}")

    _last_target: PlanTarget | None = None

    def _select_entries(
        self, entry_points: list[dict[str, Any]], target: PlanTarget
    ) -> list[dict[str, Any]]:
        self._last_target = target
        selected: dict[str, dict[str, Any]] = {}
        for entry in entry_points:
            name = entry.get("name")
            path = entry.get("file_path")
            start, end = entry.get("start_line"), entry.get("end_line")
            if not isinstance(name, str) or not isinstance(path, str):
                continue
            if name not in target.evidence_seeds and name not in (
                part.split(".")[-1] for part in target.evidence_seeds
            ):
                continue
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            if end < start or start < 1:
                continue
            key = f"{path}:{name}"
            if key not in selected or (end - start) > (
                selected[key]["end_line"] - selected[key]["start_line"]
            ):
                selected[key] = entry
        return sorted(selected.values(), key=lambda entry: entry["file_path"])

    def _read_evidence(
        self, repo: RepositorySnapshot, entry: dict[str, Any]
    ) -> EvidenceItem | None:
        path = entry.get("file_path")
        if not isinstance(path, str):
            return None
        parsed = PurePosixPath(path)
        if (
            parsed.is_absolute()
            or ".." in parsed.parts
            or path.startswith("/")
        ):
            raise ValueError(f"provider evidence path escapes root: {path}")
        local = self._root.joinpath(*parsed.parts)
        if not local.is_file() or local.is_symlink():
            return None
        if not local.resolve().is_relative_to(self._root):
            raise ValueError(f"provider evidence path escapes root: {path}")
        data = local.read_bytes()
        lines = data.splitlines(keepends=True)
        start, end = entry["start_line"], entry["end_line"]
        if end > len(lines):
            return None
        exact = b"".join(lines[start - 1 : end])
        original_text = exact.decode("utf-8", "replace")
        excerpt, _ = redact_credentials(original_text)
        content_hash = "sha256:" + hashlib.sha256(exact).hexdigest()
        symbol = entry.get("name")
        evidence_id = build_evidence_id(
            repo.repository_id,
            repo.snapshot_id,
            path,
            symbol,
            start,
            end,
            content_hash,
        )
        return EvidenceItem(
            id=evidence_id,
            provider="codewiki",
            kind="source",
            path=path,
            symbol=symbol,
            start_line=start,
            end_line=end,
            commit=repo.commit,
            content_hash=content_hash,
            excerpt_hash="sha256:"
            + hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            excerpt=excerpt,
            relationship=entry.get("reasons", ["explores"])[0]
            if entry.get("reasons")
            else "explores target symbol",
            strength="direct",
        )

    def _graph_facts(
        self, relationships: list[dict[str, Any]], target: PlanTarget
    ) -> list[GraphFact]:
        facts: list[GraphFact] = []
        seeds = set(target.evidence_seeds)
        for relation in relationships:
            source_name = relation.get("source_name")
            target_name = relation.get("target_name")
            predicate = relation.get("type")
            if not isinstance(source_name, str) or not isinstance(target_name, str):
                continue
            if not isinstance(predicate, str) or not predicate:
                continue
            if source_name not in seeds and target_name not in seeds:
                continue
            confidence = relation.get("confidence")
            facts.append(
                GraphFact(
                    source=source_name,
                    predicate=predicate,
                    target=target_name,
                    confidence="deterministic" if confidence in (None, 1.0) else "provider",
                    provenance={"repo_id": relation.get("repo_id", "")},
                )
            )
        return sorted(
            facts, key=lambda fact: (fact.source, fact.predicate, fact.target)
        )

    def _communities(
        self, relationships: list[dict[str, Any]]
    ) -> tuple[tuple[str, ...], ...]:
        adjacency: dict[str, set[str]] = {}
        for relation in relationships:
            source = relation.get("source_name")
            target = relation.get("target_name")
            if isinstance(source, str) and isinstance(target, str):
                adjacency.setdefault(source, set()).add(target)
                adjacency.setdefault(target, set()).add(source)
        seen: set[str] = set()
        communities: list[tuple[str, ...]] = []
        for node in sorted(adjacency):
            if node in seen:
                continue
            stack, component = [node], []
            seen.add(node)
            while stack:
                current = stack.pop()
                component.append(current)
                for neighbor in sorted(adjacency[current]):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            communities.append(tuple(sorted(component)))
        return tuple(communities)



__all__ = [
    "CodeWikiEvidenceProvider",
    "normalize_affected",
    "normalize_scan",
    "normalize_search",
    "normalize_update",
    "redact_credentials",
]
