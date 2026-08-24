from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any, Callable, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationInfo,
    field_validator,
    model_validator,
)

from knowledge_compiler.contracts.repository import (
    EvidenceBudget,
    PlanTarget,
    RepositorySnapshot,
)


SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
TokenCounter = Callable[[str], int]


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _normalized_posix_path(path: str) -> str:
    candidate = path.replace("\\", "/")
    parsed = PurePosixPath(candidate)
    if not candidate or parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError("evidence path must be a non-traversing relative path")
    normalized = parsed.as_posix()
    if normalized in {"", "."}:
        raise ValueError("evidence path must name a file")
    return normalized


def build_evidence_id(
    repository_id: str,
    snapshot_id: str,
    path: str,
    symbol: str | None,
    start_line: int,
    end_line: int,
    content_hash: str,
) -> str:
    normalized_path = _normalized_posix_path(path)
    return _canonical_sha256(
        [
            repository_id,
            snapshot_id,
            normalized_path,
            symbol or "",
            start_line,
            end_line,
            content_hash,
        ]
    )


class RepositorySurvey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    snapshot_id: str
    files: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    graph_communities: list[list[str]] = Field(default_factory=list)
    configuration_facts: dict[str, JsonValue] = Field(default_factory=dict)


class GraphFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    predicate: str
    target: str
    confidence: str
    provenance: dict[str, JsonValue] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    provider: str
    kind: Literal["source"] = "source"
    path: str
    symbol: str | None = None
    start_line: int = Field(gt=0)
    end_line: int = Field(gt=0)
    commit: str
    content_hash: str
    excerpt_hash: str
    excerpt: str
    relationship: str
    strength: Literal["direct"] = "direct"

    @field_validator("id", "content_hash", "excerpt_hash")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("must be a sha256:<64 lowercase hex> hash")
        return value

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return _normalized_posix_path(value)

    @model_validator(mode="after")
    def validate_line_range(self) -> EvidenceItem:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        return self


def _default_token_counter(text: str) -> int:
    return len(text.split())


class EvidencePack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["0.1"] = "0.1"
    repository: RepositorySnapshot
    target: PlanTarget
    budget: EvidenceBudget
    evidence: list[EvidenceItem] = Field(default_factory=list)
    graph_facts: list[GraphFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pack(self, info: ValidationInfo) -> EvidencePack:
        evidence_ids = [item.id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate Evidence IDs are not allowed")

        for item in self.evidence:
            if item.commit != self.repository.commit:
                raise ValueError("evidence snapshot identity mismatch: commit differs")
            expected_id = build_evidence_id(
                self.repository.repository_id,
                self.repository.snapshot_id,
                item.path,
                item.symbol,
                item.start_line,
                item.end_line,
                item.content_hash,
            )
            if item.id != expected_id:
                raise ValueError(f"Evidence ID does not match derived identity: {expected_id}")

        if len(self.evidence) > self.budget.max_items:
            raise ValueError("evidence item budget exceeded")

        model_visible_text = "".join(item.excerpt for item in self.evidence)
        if len(model_visible_text) > self.budget.max_characters:
            raise ValueError("evidence character budget exceeded")

        context: dict[str, Any] = info.context or {}
        token_counter: TokenCounter = context.get("token_counter", _default_token_counter)
        token_count = token_counter(model_visible_text)
        if not isinstance(token_count, int) or isinstance(token_count, bool) or token_count < 0:
            raise ValueError("token counter must return a nonnegative integer")
        if token_count > self.budget.max_tokens:
            raise ValueError("evidence token budget exceeded")
        return self
