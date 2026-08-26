from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from knowledge_compiler.providers.codewiki import normalize_search
from knowledge_compiler.providers.codewiki_cli import (
    CodewikiRunner,
    require_supported_version,
)


class RetirementCandidate(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    object_id: str
    evidence_paths: tuple[str, ...]
    former_symbols: tuple[str, ...]
    inbound_relations: tuple[str, ...]


class RetirementCheck(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    candidate: RetirementCandidate
    source_absent: bool
    search_complete: bool
    search_found_current: bool
    inbound_relations_verified: bool


def evaluate_retirement(check: RetirementCheck) -> bool:
    """Retire only when all four deterministic proofs hold.

    Model output, vector search, planner omission, and insufficient
    evidence never authorize deletion — only this proof set does.
    """

    return (
        check.source_absent
        and check.search_complete
        and not check.search_found_current
        and check.inbound_relations_verified
    )


class RetirementError(RuntimeError):
    """Raised when retirement cannot be committed safely."""


@dataclass(frozen=True)
class RetirementResult:
    retired: tuple[str, ...]
    blocked: tuple[str, ...]
    generation: str | None


RetirementProver = Callable[[RetirementCandidate], RetirementCheck]


class CodeWikiRetirementProver:
    """Prove absence against a freshly analyzed CodeWiki graph.

    Search is deliberately conservative: any current graph result blocks
    retirement, and existing inbound canonical relations must be regenerated
    before their target can disappear.
    """

    def __init__(self, repository_root: Path, runner: object | None = None) -> None:
        self._root = Path(repository_root).resolve()
        self._runner = runner or CodewikiRunner()
        require_supported_version(self._runner.version())
        self._indexed = False

    def __call__(self, candidate: RetirementCandidate) -> RetirementCheck:
        if not self._indexed:
            self._runner.run(
                ["codewiki", "repos", "add", str(self._root), "--json"],
                root=self._root,
            )
            self._runner.run(
                ["codewiki", "analyze", str(self._root), "--json"],
                root=self._root,
            )
            self._indexed = True
        found_current = False
        queries = tuple(
            sorted(set(candidate.former_symbols + candidate.evidence_paths))
        )
        for query in queries:
            result = self._runner.run(
                [
                    "codewiki",
                    "graph",
                    "search",
                    query,
                    "--repo",
                    str(self._root),
                    "--json",
                ],
                root=self._root,
            )
            try:
                payload = json.loads(result.stdout) if result.stdout else []
            except ValueError as error:
                raise RetirementError(
                    "CodeWiki retirement search returned invalid JSON"
                ) from error
            if not isinstance(payload, list):
                raise RetirementError(
                    "CodeWiki retirement search returned an invalid payload"
                )
            if normalize_search(payload):
                found_current = True
        return RetirementCheck(
            candidate=candidate,
            # The transaction service recomputes this proof from disk.
            source_absent=False,
            search_complete=True,
            search_found_current=found_current,
            inbound_relations_verified=not candidate.inbound_relations,
        )


def retire_proven_knowledge(
    *,
    repository_root: Path,
    candidate_ids: set[str],
    prover: RetirementProver,
) -> RetirementResult:
    """Delete only stale objects that pass all deterministic proofs."""

    from knowledge_compiler.incremental.invalidation import (
        load_generation_knowledge,
    )

    root = Path(repository_root).resolve()
    objects, packs = load_generation_knowledge(root)
    approved: list[str] = []
    blocked: list[str] = []
    for object_id in sorted(candidate_ids):
        canonical = objects.get(object_id)
        pack = packs.get(object_id)
        if (
            canonical is None
            or canonical.validity.status != "stale"
            or pack is None
        ):
            blocked.append(object_id)
            continue
        paths = tuple(sorted({item.path for item in pack.evidence}))
        symbols = tuple(
            sorted({item.symbol for item in pack.evidence if item.symbol})
        )
        candidate = RetirementCandidate(
            object_id=object_id,
            evidence_paths=paths,
            former_symbols=symbols,
            inbound_relations=_inbound_relations(objects, object_id),
        )
        source_absent = bool(paths) and all(
            not root.joinpath(*Path(path).parts).exists() for path in paths
        )
        check = RetirementCheck.model_validate(
            prover(candidate).model_dump(mode="json")
        )
        if check.candidate != candidate:
            raise RetirementError("retirement prover changed candidate identity")
        check = check.model_copy(update={"source_absent": source_absent})
        if evaluate_retirement(check):
            approved.append(object_id)
        else:
            blocked.append(object_id)

    if not approved:
        return RetirementResult(
            retired=(), blocked=tuple(blocked), generation=None
        )
    remaining = {
        object_id: canonical
        for object_id, canonical in objects.items()
        if object_id not in approved
    }
    items = tuple(
        (canonical, packs.get(object_id))
        for object_id, canonical in sorted(remaining.items())
    )
    try:
        manifest = yaml.safe_load(
            (root / ".knowledge/manifest.yaml").read_bytes()
        )
        active = manifest["active_generation"]
    except (KeyError, OSError, ValueError, yaml.YAMLError) as error:
        raise RetirementError(f"manifest unreadable: {error}") from error
    generation = "gen-retire-" + hashlib.sha256(
        json.dumps(
            [active, sorted(approved)], separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()[:24]
    from knowledge_compiler.storage import GenerationPublisher, PublicationError

    try:
        GenerationPublisher(root).publish_generation(
            generation, items, allow_empty=not items
        )
    except PublicationError as error:
        raise RetirementError(str(error)) from error
    from knowledge_compiler.incremental.pending import PendingStore

    pending = PendingStore(root / ".knowledge/state/pending-targets.json")
    for object_id in approved:
        pending.resolve(object_id)
    return RetirementResult(
        retired=tuple(approved),
        blocked=tuple(blocked),
        generation=generation,
    )


def _inbound_relations(
    objects: dict[str, object], target_id: str
) -> tuple[str, ...]:
    inbound: set[str] = set()
    for object_id, canonical in objects.items():
        if object_id == target_id:
            continue
        targets: set[str] = set()
        for field in ("dependencies", "relations", "relationships"):
            for item in getattr(canonical, field, ()):
                target = getattr(item, "target", None)
                if isinstance(target, str):
                    targets.add(target)
        for target in getattr(canonical, "related_objects", ()):
            if isinstance(target, str):
                targets.add(target)
        if target_id in targets:
            inbound.add(object_id)
    return tuple(sorted(inbound))


__all__ = [
    "RetirementCandidate",
    "RetirementCheck",
    "CodeWikiRetirementProver",
    "RetirementError",
    "RetirementResult",
    "evaluate_retirement",
    "retire_proven_knowledge",
]
