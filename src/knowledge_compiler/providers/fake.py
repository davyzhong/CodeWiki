from __future__ import annotations

import json
import re
from json import JSONDecodeError
from pathlib import Path, PurePosixPath
from typing import Any

from knowledge_compiler.contracts import (
    EvidenceBudget,
    EvidenceItem,
    EvidencePack,
    PlanTarget,
    RepositorySnapshot,
    RepositorySurvey,
)
from knowledge_compiler.providers.base import IndexStatus


class FakeEvidenceProvider:
    """Load deterministic project-owned evidence from normalized JSON fixtures."""

    def __init__(self, *, fixture_dir: Path, repository_root: Path) -> None:
        fixture_dir = Path(fixture_dir)
        repository_root = Path(repository_root)
        if not fixture_dir.is_absolute():
            raise ValueError("fixture_dir must be absolute")
        if not repository_root.is_absolute():
            raise ValueError("repository_root must be absolute")

        self._fixture_dir = fixture_dir.resolve()
        self._repository_root = repository_root.resolve()

        survey_payload = self._load_json(self._fixture_dir / "survey.json")
        pack_payload = self._load_json(self._fixture_dir / "evidence-pack.json")
        repository_payload = pack_payload.get("repository")
        if not isinstance(repository_payload, dict):
            raise ValueError("evidence-pack fixture repository must be an object")
        if repository_payload.get("root") != ".":
            raise ValueError('fixture repository root must be the portable marker "."')

        bound_pack_payload = dict(pack_payload)
        bound_pack_payload["repository"] = {
            **repository_payload,
            "root": self._repository_root,
        }
        self._survey = RepositorySurvey.model_validate(survey_payload)
        self._pack = EvidencePack.model_validate(bound_pack_payload)
        self._validate_fixture_bindings()
        self._evidence_by_id = {item.id: item for item in self._pack.evidence}

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=reject_duplicate_keys,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-finite JSON number: {value}")
                ),
            )
        except (JSONDecodeError, OSError, UnicodeError, ValueError) as error:
            raise ValueError(f"invalid fixture JSON at {path.name}: {error}") from error
        if not isinstance(payload, dict):
            raise ValueError(f"fixture JSON at {path.name} must contain an object")
        return payload

    def _validate_fixture_bindings(self) -> None:
        repository = self._pack.repository
        if self._survey.repository_id != repository.repository_id:
            raise ValueError("fixture repository identity mismatch")
        if self._survey.snapshot_id != repository.snapshot_id:
            raise ValueError("fixture snapshot mismatch")
        eligible_files = set(repository.eligible_files)
        for survey_file in self._survey.files:
            self._validate_survey_path(survey_file)
            if survey_file not in eligible_files:
                raise ValueError(
                    f"survey file is not repository-eligible: {survey_file}"
                )
        for item in self._pack.evidence:
            candidate = self._repository_root.joinpath(*Path(item.path).parts)
            if not candidate.is_relative_to(self._repository_root):
                raise ValueError(
                    f"fixture evidence path escapes bound repository root: {item.path}"
                )

    @staticmethod
    def _validate_survey_path(path: str) -> None:
        parsed = PurePosixPath(path)
        if (
            not path
            or "\x00" in path
            or "\\" in path
            or re.match(r"^[A-Za-z]:", path)
            or parsed.is_absolute()
            or ".." in parsed.parts
            or parsed.as_posix() in {"", "."}
            or parsed.as_posix() != path
        ):
            raise ValueError(
                f"survey file must be a normalized repository-relative POSIX path: {path}"
            )

    def _validate_repository(self, repo: RepositorySnapshot) -> RepositorySnapshot:
        repo = RepositorySnapshot.model_validate(repo)
        expected = self._pack.repository
        if repo.repository_id != expected.repository_id:
            raise ValueError("repository identity mismatch")
        if repo.root.resolve() != self._repository_root:
            raise ValueError("repository root mismatch")
        if repo.snapshot_id != expected.snapshot_id:
            raise ValueError("snapshot mismatch")
        if repo != expected:
            raise ValueError("repository snapshot metadata mismatch")
        return repo

    def inspect(self, repo: RepositorySnapshot) -> RepositorySurvey:
        self._validate_repository(repo)
        return RepositorySurvey.model_validate(self._survey.model_dump())

    def ensure_index(self, repo: RepositorySnapshot) -> IndexStatus:
        validated = self._validate_repository(repo)
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
        validated_repo = self._validate_repository(repo)
        target = PlanTarget.model_validate(target)
        budget = EvidenceBudget.model_validate(budget)
        if target != self._pack.target:
            raise ValueError("target mismatch")
        payload = self._pack.model_dump()
        payload["repository"] = validated_repo
        payload["budget"] = budget
        return EvidencePack.model_validate(payload)

    def get_evidence(
        self,
        repo: RepositorySnapshot,
        evidence_id: str,
    ) -> EvidenceItem:
        self._validate_repository(repo)
        try:
            item = self._evidence_by_id[evidence_id]
        except KeyError as error:
            raise KeyError(f"unknown Evidence ID: {evidence_id}") from error
        return EvidenceItem.model_validate(item.model_dump())
