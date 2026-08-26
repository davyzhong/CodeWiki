from __future__ import annotations

import json
import os
import re
from pathlib import Path

from knowledge_compiler.orchestrator.contracts import RunRecord


_SAFE_COMPONENT = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,254}[A-Za-z0-9_-])?\Z"
)


class RunStoreError(ValueError):
    """Raised when persisted run state cannot be saved or trusted."""


class RunStore:
    """Atomic single-active-run store under .knowledge/state/runs/<run-id>/."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)

    def _run_dir(self, run_id: str) -> Path:
        if not _SAFE_COMPONENT.fullmatch(run_id) or run_id in {".", ".."}:
            raise RunStoreError(f"unsafe run id: {run_id}")
        return self._root / run_id

    def _target_dir(self, run_id: str, target_id: str) -> Path:
        if (
            not _SAFE_COMPONENT.fullmatch(target_id)
            or target_id in {".", ".."}
        ):
            raise RunStoreError(f"unsafe target id: {target_id}")
        return self._run_dir(run_id) / "targets" / target_id

    def save(self, record: RunRecord) -> None:
        record = RunRecord.model_validate(record.model_dump(mode="json"))
        if record.active:
            for existing in self._list_runs():
                if existing.run_id == record.run_id:
                    continue
                if existing.active:
                    raise RunStoreError(
                        "another active run holds the state: "
                        f"{existing.run_id}"
                    )
        run_dir = self._run_dir(record.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        )
        temporary = run_dir / "run.json.tmp"
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, run_dir / "run.json")

    def load(self, run_id: str) -> RunRecord:
        file = self._run_dir(run_id) / "run.json"
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise RunStoreError(f"run state unreadable: {error}") from error
        try:
            return RunRecord.model_validate(payload)
        except ValueError as error:
            raise RunStoreError(f"run state is tampered or invalid: {error}") from error

    def save_extraction_context(
        self,
        run_id: str,
        target_id: str,
        request: object,
        result: object,
    ) -> None:
        from knowledge_compiler.contracts.knowledge import ExtractionResult
        from knowledge_compiler.contracts.semantic import ExtractionRequest

        validated_request = ExtractionRequest.model_validate(
            request.model_dump(mode="json")
        )
        validated_result = ExtractionResult.model_validate(
            result.model_dump(mode="json")
        )
        if (
            validated_request.run_id != run_id
            or validated_request.target_id != target_id
            or validated_result.run_id != run_id
            or validated_result.target_id != target_id
        ):
            raise RunStoreError(
                "extraction context identity does not match its run target"
            )
        target_dir = self._target_dir(run_id, target_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "request": validated_request.model_dump(mode="json"),
                "result": validated_result.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        temporary = target_dir / "extraction.json.tmp"
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, target_dir / "extraction.json")

    def save_plan(self, run_id: str, plan: object) -> None:
        from knowledge_compiler.contracts.planning import KnowledgePlan

        validated = KnowledgePlan.model_validate(plan.model_dump(mode="json"))
        if validated.run_id != run_id:
            raise RunStoreError("plan identity does not match its run")
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        temporary = run_dir / "plan.json.tmp"
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, run_dir / "plan.json")

    def save_preserved_artifacts(
        self,
        run_id: str,
        items: tuple[tuple[object, object | None], ...],
    ) -> None:
        from knowledge_compiler.contracts.canonical import (
            parse_canonical_knowledge,
        )
        from knowledge_compiler.contracts.evidence import EvidencePack

        payload: list[dict[str, object]] = []
        for canonical, pack in items:
            validated = parse_canonical_knowledge(
                canonical.model_dump(mode="json")
            )
            validated_pack = (
                EvidencePack.model_validate(pack.model_dump(mode="json"))
                if pack is not None
                else None
            )
            if validated.validity.status != "verified":
                raise RunStoreError("only verified objects may be preserved")
            if validated.type == "module" and validated_pack is None:
                raise RunStoreError("preserved modules require an Evidence Pack")
            if validated_pack is not None and validated_pack.target.id != validated.id:
                raise RunStoreError("preserved artifact identities differ")
            payload.append(
                {
                    "canonical": validated.model_dump(mode="json"),
                    "evidence_pack": (
                        validated_pack.model_dump(mode="json")
                        if validated_pack is not None
                        else None
                    ),
                }
            )
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        temporary = run_dir / "preserved.json.tmp"
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, run_dir / "preserved.json")

    def load_preserved_artifacts(
        self, run_id: str
    ) -> tuple[tuple[object, object | None], ...]:
        from knowledge_compiler.contracts.canonical import (
            parse_canonical_knowledge,
        )
        from knowledge_compiler.contracts.evidence import EvidencePack

        path = self._run_dir(run_id) / "preserved.json"
        if not path.exists():
            return ()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("preserved artifacts must be a list")
            items = tuple(
                (
                    parse_canonical_knowledge(item["canonical"]),
                    (
                        EvidencePack.model_validate(item["evidence_pack"])
                        if item.get("evidence_pack") is not None
                        else None
                    ),
                )
                for item in payload
            )
        except (KeyError, OSError, ValueError) as error:
            raise RunStoreError(
                f"preserved artifacts unreadable: {error}"
            ) from error
        return items

    def save_evidence_pack(
        self, run_id: str, target_id: str, pack: object
    ) -> None:
        from knowledge_compiler.contracts.evidence import EvidencePack

        validated = EvidencePack.model_validate(pack.model_dump(mode="json"))
        if validated.target.id != target_id:
            raise RunStoreError("evidence pack identity does not match its target")
        target_dir = self._target_dir(run_id, target_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        temporary = target_dir / "evidence.json.tmp"
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, target_dir / "evidence.json")

    def load_evidence_pack(self, run_id: str, target_id: str) -> object:
        from knowledge_compiler.contracts.evidence import EvidencePack

        path = self._target_dir(run_id, target_id) / "evidence.json"
        try:
            pack = EvidencePack.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            raise RunStoreError(f"evidence pack unreadable: {error}") from error
        if pack.target.id != target_id:
            raise RunStoreError("evidence pack identity does not match its target")
        return pack

    def save_verified_artifact(
        self,
        run_id: str,
        target_id: str,
        canonical: object,
        pack: object,
    ) -> None:
        from knowledge_compiler.contracts.evidence import EvidencePack

        validated_pack = EvidencePack.model_validate(pack.model_dump(mode="json"))
        validated_object = _canonical_object(canonical.model_dump(mode="json"))
        if (
            validated_object.id != target_id
            or validated_pack.target.id != target_id
        ):
            raise RunStoreError("verified artifact identity does not match its target")
        target_dir = self._target_dir(run_id, target_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "canonical": validated_object.model_dump(mode="json"),
                "evidence_pack": validated_pack.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        temporary = target_dir / "verified.json.tmp"
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, target_dir / "verified.json")

    def load_verified_artifact(
        self, run_id: str, target_id: str
    ) -> tuple[object, object]:
        from knowledge_compiler.contracts.evidence import EvidencePack

        path = self._target_dir(run_id, target_id) / "verified.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            canonical = _canonical_object(payload["canonical"])
            pack = EvidencePack.model_validate(payload["evidence_pack"])
        except (KeyError, OSError, ValueError) as error:
            raise RunStoreError(f"verified artifact unreadable: {error}") from error
        if canonical.id != target_id or pack.target.id != target_id:
            raise RunStoreError("verified artifact identity does not match its target")
        return canonical, pack

    def load_extraction_context(
        self, run_id: str, target_id: str
    ) -> tuple[object, object]:
        from knowledge_compiler.contracts.knowledge import ExtractionResult
        from knowledge_compiler.contracts.semantic import ExtractionRequest

        path = self._target_dir(run_id, target_id) / "extraction.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            request = ExtractionRequest.model_validate(payload["request"])
            result = ExtractionResult.model_validate(payload["result"])
        except (KeyError, OSError, ValueError) as error:
            raise RunStoreError(
                f"extraction context unreadable: {error}"
            ) from error
        if (
            request.run_id != run_id
            or request.target_id != target_id
            or result.run_id != run_id
            or result.target_id != target_id
        ):
            raise RunStoreError(
                "extraction context identity does not match its run target"
            )
        return request, result

    def _list_runs(self) -> list[RunRecord]:
        records: list[RunRecord] = []
        if not self._root.exists():
            return records
        for directory in sorted(self._root.iterdir()):
            if not directory.is_dir() or directory.is_symlink():
                continue
            file = directory / "run.json"
            if not file.exists():
                continue
            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
                records.append(RunRecord.model_validate(payload))
            except (OSError, ValueError):
                continue
        return records

    def active_run(self) -> RunRecord | None:
        for record in self._list_runs():
            if record.active:
                return record
        return None


def _canonical_object(payload: object) -> object:
    from knowledge_compiler.contracts.knowledge import (
        ArchitectureKnowledge,
        FlowKnowledge,
        ModuleKnowledge,
        RuleKnowledge,
        TechStackKnowledge,
    )

    if not isinstance(payload, dict):
        raise ValueError("canonical object must be a mapping")
    models = {
        "architecture": ArchitectureKnowledge,
        "module": ModuleKnowledge,
        "flow": FlowKnowledge,
        "rule": RuleKnowledge,
        "tech-stack": TechStackKnowledge,
    }
    model = models.get(payload.get("type"))
    if model is None:
        raise ValueError("unknown canonical object type")
    return model.model_validate(payload)


__all__ = ["RunStore", "RunStoreError"]
