from __future__ import annotations

import errno
import json
import os
import re
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from knowledge_compiler.compiler import (
    compile_module_card,
    compile_module_wiki,
    compile_module_yaml,
)
from knowledge_compiler.contracts.evidence import EvidencePack
from knowledge_compiler.contracts.knowledge import ModuleKnowledge


_GENERATION = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?\Z"
)
_OUTPUTS = (
    ("canonical", "objects/modules", ".yaml"),
    ("card", "views/cards", ".md"),
    ("wiki", "views/wiki", ".md"),
)

_TYPE_DIRECTORIES = {
    "module": "modules",
    "architecture": "architecture",
    "flow": "flows",
    "rule": "rules",
    "tech-stack": "tech-stack",
}


def _object_type(model: object) -> str:
    from knowledge_compiler.contracts.knowledge import (
        ArchitectureKnowledge,
        FlowKnowledge,
        RuleKnowledge,
        TechStackKnowledge,
    )

    if isinstance(
        model,
        ArchitectureKnowledge
        | FlowKnowledge
        | RuleKnowledge
        | TechStackKnowledge,
    ):
        return model.type
    return "module"


def _compile_outputs(model: object, evidence_pack: object) -> dict[str, bytes]:
    """Precompile canonical, card, and wiki bytes for any typed object."""
    from knowledge_compiler.compiler.typed_views import compile_typed_wiki
    from knowledge_compiler.compiler.yaml import (
        compile_architecture_yaml,
        compile_flow_yaml,
        compile_module_yaml,
        compile_rule_card,
        compile_rule_yaml,
        compile_tech_stack_card,
        compile_tech_stack_yaml,
    )

    object_type = _object_type(model)
    if object_type == "module":
        return {
            "canonical": compile_module_yaml(model, evidence_pack),
            "card": None,  # module card needs the pack below
            "wiki": None,
        }
    yaml_compilers = {
        "architecture": compile_architecture_yaml,
        "flow": compile_flow_yaml,
        "rule": compile_rule_yaml,
        "tech-stack": compile_tech_stack_yaml,
    }
    card_compilers = {
        "rule": compile_rule_card,
        "tech-stack": compile_tech_stack_card,
    }
    canonical = yaml_compilers[object_type](model)
    card = card_compilers.get(object_type)
    return {
        "canonical": canonical,
        "card": card(model) if card else compile_typed_wiki(model),
        "wiki": compile_typed_wiki(model),
    }


def _compile_stale_outputs(model: object) -> dict[str, bytes | None]:
    """Compile a stale canonical while excluding it from safe Agent views."""

    validated = model.__class__.model_validate(model.model_dump(mode="json"))
    if validated.validity.status != "stale":
        raise ValueError("stale compilation requires stale validity")
    canonical = yaml.safe_dump(
        validated.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    ).encode("utf-8")
    return {
        "canonical": canonical,
        "card": None,
        # Human Wiki compilation is a later, independently stamped view.
        "wiki": None,
    }


class PublicationError(RuntimeError):
    """Raised when a generation cannot be safely published or recovered."""


@dataclass(frozen=True)
class PublishedGeneration:
    generation: str
    canonical_path: Path
    card_path: Path
    wiki_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class PublishedObject:
    object_id: str
    object_type: str
    canonical_path: Path
    card_path: Path
    wiki_path: Path


@dataclass(frozen=True)
class PublishedGenerationBatch:
    generation: str
    objects: tuple[PublishedObject, ...]
    manifest_path: Path


class GenerationPublisher:
    """Publish one module generation with a durable rollback journal.

    M1 publication is intentionally single-process. Every managed directory is
    rejected if it is a symlink, and regular files are opened with O_NOFOLLOW
    where the platform provides it. Coordinating two publishers, or defending
    against an administrator concurrently replacing managed directories, is out
    of the M1 scope; later orchestration must add a repository publication lock.
    """

    def __init__(
        self,
        output_root: str | os.PathLike[str],
        *,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.output_root = Path(output_root).absolute()
        self.knowledge_root = self.output_root / ".knowledge"
        self.transactions_root = self.knowledge_root / "state/transactions"
        self._inject = fault_injector or (lambda _point: None)

    def publish(
        self,
        generation: str,
        module: ModuleKnowledge,
        evidence_pack: EvidencePack | None = None,
    ) -> PublishedGeneration:
        self._validate_generation(generation)
        object_type = _object_type(module)
        if object_type == "module" and evidence_pack is None:
            raise PublicationError("module publication requires an evidence pack")
        try:
            # Compilation and contract revalidation must complete before the first
            # output-directory mutation.
            if object_type == "module":
                compiled = {
                    "canonical": compile_module_yaml(module, evidence_pack),
                    "card": compile_module_card(module, evidence_pack),
                    "wiki": compile_module_wiki(module, evidence_pack),
                }
            else:
                compiled = _compile_outputs(module, None)
            manifest = yaml.safe_dump(
                {
                    "active_generation": generation,
                    "agent_views_generation": generation,
                    "wiki_generation": generation,
                },
                sort_keys=False,
                allow_unicode=True,
            ).encode("utf-8")
        except Exception as error:
            raise PublicationError(f"generation compilation failed: {error}") from error

        payloads = {**compiled, "manifest": manifest}
        module_id = self._safe_object_id(module)
        object_type = _object_type(module)
        destinations = self._destinations(module_id, object_type)
        transaction = self.transactions_root / generation
        # A generation id names one committed content set. Republishing the
        # same id with differing bytes would let a later recovery mistake a
        # partially replaced tree for a committed one, so reject the
        # ambiguity before the first mutation.
        try:
            if self._manifest_generation() == generation:
                for name, destination in destinations.items():
                    if not self._lexists(destination) or self._read_regular(
                        destination
                    ) != payloads[name]:
                        raise PublicationError(
                            "generation id reuse with missing or differing "
                            "content: " + name
                        )
        except PublicationError:
            raise
        except OSError as error:
            raise PublicationError(f"generation reuse check failed: {error}") from error
        try:
            self._assert_safe_roots(create=True)
            # Any pending journal must be recovered before a new publication:
            # layering transactions would let a later recovery roll a committed
            # generation back or accept a mixed tree.
            if any(self.transactions_root.iterdir()):
                raise PublicationError(
                    "unrecovered transactions exist; run recovery before publishing"
                )
            self._mkdir(transaction)
            stage = transaction / "stage"
            backup = transaction / "backup"
            self._mkdir(stage)
            self._mkdir(backup)

            staged: dict[str, Path] = {}
            for name, data in payloads.items():
                path = stage / name
                self._write_bytes(path, data, f"stage.{name}")
                staged[name] = path
            self._fsync_directory(stage, "stage.directory.fsync")

            entries: list[dict[str, Any]] = []
            for name, destination in destinations.items():
                self._ensure_managed_parent(destination.parent)
                backup_path = backup / name
                had_destination = self._lexists(destination)
                if had_destination:
                    old_bytes = self._read_regular(destination)
                    self._write_bytes(backup_path, old_bytes, f"backup.{name}")
                entries.append(
                    {
                        "name": name,
                        "destination": str(destination.relative_to(self.knowledge_root)),
                        "staged": str(staged[name].relative_to(transaction)),
                        "backup": str(backup_path.relative_to(transaction)),
                        "had_destination": had_destination,
                    }
                )
            self._fsync_directory(backup, "backup.directory.fsync")

            journal = {
                "schema_version": 1,
                "generation": generation,
                "object_id": module_id,
                "object_type": object_type,
                "entries": entries,
            }
            journal_bytes = (
                json.dumps(journal, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            journal_temporary = transaction / "journal.tmp"
            self._write_bytes(journal_temporary, journal_bytes, "journal")
            self._inject("journal.replace")
            os.replace(journal_temporary, transaction / "journal.json")
            self._fsync_directory(transaction, "transaction.directory.fsync")

            # Canonical/Card/Wiki become visible first. The manifest is the sole
            # generation commit marker and is deliberately replaced last.
            for name in ("canonical", "card", "wiki", "manifest"):
                destination = destinations[name]
                self._ensure_managed_parent(destination.parent)
                self._inject(f"publish.{name}.replace")
                os.replace(staged[name], destination)
                self._fsync_directory(
                    destination.parent, f"publish.{name}.directory.fsync"
                )
        except Exception as error:
            if isinstance(error, PublicationError):
                raise
            raise PublicationError(f"publication failed at {error}") from error

        # Once manifest replacement is durable, cleanup is housekeeping. A crash
        # here is recognized as committed and cleaned by recover().
        try:
            self._remove_transaction(transaction)
        except Exception as error:
            if isinstance(error, PublicationError):
                raise
            raise PublicationError(f"publication cleanup failed: {error}") from error
        return PublishedGeneration(
            generation=generation,
            canonical_path=destinations["canonical"],
            card_path=destinations["card"],
            wiki_path=destinations["wiki"],
            manifest_path=destinations["manifest"],
        )

    def publish_generation(
        self,
        generation: str,
        items: tuple[tuple[object, EvidencePack | None], ...],
        *,
        allow_empty: bool = False,
    ) -> PublishedGenerationBatch:
        """Publish a complete multi-object generation in one transaction."""

        self._validate_generation(generation)
        if not items and not allow_empty:
            raise PublicationError("generation must contain at least one object")

        prepared: list[
            tuple[str, str, dict[str, bytes | None], dict[str, Path]]
        ] = []
        seen_ids: set[str] = set()
        contains_stale = False
        try:
            for model, evidence_pack in items:
                object_id = self._safe_object_id(model)
                object_type = _object_type(model)
                if object_id in seen_ids:
                    raise PublicationError(
                        f"duplicate object id in generation: {object_id}"
                    )
                seen_ids.add(object_id)
                if model.validity.status == "stale":
                    contains_stale = True
                    compiled = _compile_stale_outputs(model)
                elif object_type == "module":
                    if evidence_pack is None:
                        raise PublicationError(
                            "module publication requires an evidence pack"
                        )
                    compiled = {
                        "canonical": compile_module_yaml(model, evidence_pack),
                        "card": compile_module_card(model, evidence_pack),
                        "wiki": compile_module_wiki(model, evidence_pack),
                    }
                else:
                    compiled = _compile_outputs(model, None)
                destinations = self._destinations(object_id, object_type)
                if compiled["wiki"] is None:
                    if not self._lexists(destinations["wiki"]):
                        raise PublicationError(
                            f"stale Wiki source is unavailable: {object_id}"
                        )
                    compiled["wiki"] = self._read_regular(
                        destinations["wiki"]
                    )
                prepared.append(
                    (
                        object_id,
                        object_type,
                        compiled,
                        destinations,
                    )
                )
            prepared.sort(key=lambda item: (item[1], item[0]))
            manifest = yaml.safe_dump(
                {
                    "active_generation": generation,
                    "agent_views_generation": generation,
                    "wiki_generation": (
                        self._manifest_value("wiki_generation")
                        if contains_stale
                        else generation
                    ),
                    "objects": [
                        {"id": object_id, "type": object_type}
                        for object_id, object_type, _, _ in prepared
                    ],
                },
                sort_keys=False,
                allow_unicode=True,
            ).encode("utf-8")
        except PublicationError:
            raise
        except Exception as error:
            raise PublicationError(
                f"generation compilation failed: {error}"
            ) from error

        payload_entries: list[dict[str, Any]] = []
        for index, (object_id, object_type, compiled, destinations) in enumerate(
            prepared
        ):
            for kind in ("canonical", "card", "wiki"):
                payload_entries.append(
                    {
                        "name": f"{index:04d}-{kind}",
                        "kind": kind,
                        "object_id": object_id,
                        "object_type": object_type,
                        "action": (
                            "delete" if compiled[kind] is None else "replace"
                        ),
                        "data": compiled[kind],
                        "destination": destinations[kind],
                    }
                )
        current_identities = {
            (object_id, object_type)
            for object_id, object_type, _, _ in prepared
        }
        removed_identities = tuple(
            sorted(set(self._manifest_objects()) - current_identities)
        )
        for index, (object_id, object_type) in enumerate(removed_identities):
            destinations = self._destinations(object_id, object_type)
            for kind in ("canonical", "card", "wiki"):
                payload_entries.append(
                    {
                        "name": f"removed-{index:04d}-{kind}",
                        "kind": kind,
                        "object_id": object_id,
                        "object_type": object_type,
                        "action": "delete",
                        "data": None,
                        "destination": destinations[kind],
                    }
                )
        manifest_path = self.knowledge_root / "manifest.yaml"
        payload_entries.append(
            {
                "name": "manifest",
                "kind": "manifest",
                "object_id": None,
                "object_type": None,
                "action": "replace",
                "data": manifest,
                "destination": manifest_path,
            }
        )

        try:
            if self._manifest_generation() == generation:
                for entry in payload_entries:
                    if entry["action"] == "delete":
                        if self._lexists(entry["destination"]):
                            raise PublicationError(
                                "generation id reuse with unexpected content: "
                                f"{entry['name']}"
                            )
                        continue
                    destination = entry["destination"]
                    if not self._lexists(destination) or self._read_regular(
                        destination
                    ) != entry["data"]:
                        raise PublicationError(
                            "generation id reuse with missing or differing "
                            f"content: {entry['name']}"
                        )
                return self._batch_result(generation, prepared, manifest_path)
        except PublicationError:
            raise
        except OSError as error:
            raise PublicationError(
                f"generation reuse check failed: {error}"
            ) from error

        transaction = self.transactions_root / generation
        try:
            self._assert_safe_roots(create=True)
            if any(self.transactions_root.iterdir()):
                raise PublicationError(
                    "unrecovered transactions exist; run recovery before publishing"
                )
            self._mkdir(transaction)
            stage = transaction / "stage"
            backup = transaction / "backup"
            self._mkdir(stage)
            self._mkdir(backup)

            for entry in payload_entries:
                if entry["action"] == "delete":
                    entry["staged_path"] = None
                    continue
                staged = stage / entry["name"]
                self._write_bytes(
                    staged, entry["data"], f"stage.{entry['kind']}"
                )
                entry["staged_path"] = staged
            self._fsync_directory(stage, "stage.directory.fsync")

            journal_entries: list[dict[str, Any]] = []
            for entry in payload_entries:
                destination = entry["destination"]
                self._ensure_managed_parent(destination.parent)
                backup_path = backup / entry["name"]
                had_destination = self._lexists(destination)
                if had_destination:
                    self._write_bytes(
                        backup_path,
                        self._read_regular(destination),
                        f"backup.{entry['kind']}",
                    )
                journal_entries.append(
                    {
                        "name": entry["name"],
                        "kind": entry["kind"],
                        "object_id": entry["object_id"],
                        "object_type": entry["object_type"],
                        "action": entry["action"],
                        "destination": str(
                            destination.relative_to(self.knowledge_root)
                        ),
                        "staged": (
                            str(entry["staged_path"].relative_to(transaction))
                            if entry["staged_path"] is not None
                            else None
                        ),
                        "backup": str(backup_path.relative_to(transaction)),
                        "had_destination": had_destination,
                    }
                )
            self._fsync_directory(backup, "backup.directory.fsync")

            journal = {
                "schema_version": 2,
                "generation": generation,
                "allow_empty": allow_empty,
                "objects": [
                    {"id": object_id, "type": object_type}
                    for object_id, object_type, _, _ in prepared
                ],
                "removed_objects": [
                    {"id": object_id, "type": object_type}
                    for object_id, object_type in removed_identities
                ],
                "entries": journal_entries,
            }
            journal_bytes = (
                json.dumps(journal, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
            journal_temporary = transaction / "journal.tmp"
            self._write_bytes(journal_temporary, journal_bytes, "journal")
            self._inject("journal.replace")
            os.replace(journal_temporary, transaction / "journal.json")
            self._fsync_directory(transaction, "transaction.directory.fsync")

            for entry in payload_entries:
                destination = entry["destination"]
                self._ensure_managed_parent(destination.parent)
                if entry["action"] == "delete":
                    self._inject(f"publish.{entry['kind']}.delete")
                    if self._lexists(destination):
                        self._unlink_file(destination)
                else:
                    self._inject(f"publish.{entry['kind']}.replace")
                    os.replace(entry["staged_path"], destination)
                self._fsync_directory(
                    destination.parent,
                    f"publish.{entry['kind']}.directory.fsync",
                )
        except Exception as error:
            if isinstance(error, PublicationError):
                raise
            raise PublicationError(f"publication failed at {error}") from error

        try:
            self._remove_transaction(transaction)
        except Exception as error:
            if isinstance(error, PublicationError):
                raise
            raise PublicationError(f"publication cleanup failed: {error}") from error
        return self._batch_result(generation, prepared, manifest_path)

    @staticmethod
    def _batch_result(
        generation: str,
        prepared: list[
            tuple[str, str, dict[str, bytes | None], dict[str, Path]]
        ],
        manifest_path: Path,
    ) -> PublishedGenerationBatch:
        return PublishedGenerationBatch(
            generation=generation,
            objects=tuple(
                PublishedObject(
                    object_id=object_id,
                    object_type=object_type,
                    canonical_path=destinations["canonical"],
                    card_path=destinations["card"],
                    wiki_path=destinations["wiki"],
                )
                for object_id, object_type, _, destinations in prepared
            ),
            manifest_path=manifest_path,
        )

    def recover(self) -> None:
        """Recover every incomplete journal; safe to repeat after interruption."""

        try:
            self._assert_safe_roots(create=False)
            if not self.transactions_root.exists():
                return
            for transaction in sorted(self.transactions_root.iterdir()):
                if transaction.is_symlink() or not transaction.is_dir():
                    # Leave stray entries untouched; the next publish refuses
                    # to run until they are investigated and removed.
                    continue
                self._recover_transaction(transaction)
        except Exception as error:
            if isinstance(error, PublicationError):
                raise
            raise PublicationError(f"recovery failed at {error}") from error

    def _recover_transaction(self, transaction: Path) -> None:
        journal_path = transaction / "journal.json"
        if not journal_path.exists():
            self._remove_transaction(transaction)
            return
        try:
            journal = json.loads(self._read_regular(journal_path))
            generation = journal["generation"]
            self._validate_generation(generation)
            schema_version = journal.get("schema_version")
            if schema_version == 2:
                if generation != transaction.name:
                    raise PublicationError(
                        "transaction journal identity is invalid"
                    )
                self._recover_batch_transaction(
                    transaction, journal, generation
                )
                return
            if (
                generation != transaction.name
                or type(schema_version) is not int
                or schema_version != 1
            ):
                raise PublicationError("transaction journal identity is invalid")
            module_id = journal["object_id"]
            object_type = journal.get("object_type", "module")
            if object_type not in _TYPE_DIRECTORIES:
                raise PublicationError("transaction journal object type is invalid")
            expected = self._destinations(
                self._validate_object_id(module_id), object_type
            )
            entries = journal["entries"]
            if not isinstance(entries, list) or len(entries) != 4:
                raise PublicationError("transaction journal entries are invalid")
            by_name = {entry.get("name"): entry for entry in entries}
            if set(by_name) != set(expected):
                raise PublicationError("transaction journal destinations are invalid")
            for name, destination in expected.items():
                entry = by_name[name]
                if entry.get("destination") != str(
                    destination.relative_to(self.knowledge_root)
                ):
                    raise PublicationError("transaction journal destination escaped root")
                if entry.get("backup") != f"backup/{name}":
                    raise PublicationError("transaction journal backup escaped root")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PublicationError("transaction journal is malformed") from error

        if self._manifest_generation() == generation:
            self._remove_transaction(transaction)
            return

        for name in ("canonical", "card", "wiki", "manifest"):
            destination = expected[name]
            entry = by_name[name]
            self._ensure_managed_parent(destination.parent)
            if entry.get("had_destination") is True:
                backup = transaction / "backup" / name
                data = self._read_regular(backup)
                restore = transaction / f"restore-{name}"
                if self._lexists(restore):
                    self._unlink_file(restore)
                self._write_bytes(restore, data, f"recovery.{name}.stage")
                self._inject(f"recovery.{name}.replace")
                os.replace(restore, destination)
            elif entry.get("had_destination") is False:
                if self._lexists(destination):
                    self._unlink_file(destination)
            else:
                raise PublicationError("transaction journal backup flag is invalid")
            self._fsync_directory(
                destination.parent, f"recovery.{name}.directory.fsync"
            )
        self._remove_transaction(transaction)

    def _recover_batch_transaction(
        self,
        transaction: Path,
        journal: dict[str, Any],
        generation: str,
    ) -> None:
        objects = journal.get("objects")
        removed_objects = journal.get("removed_objects", [])
        entries = journal.get("entries")
        allow_empty = journal.get("allow_empty", False)
        if not isinstance(allow_empty, bool):
            raise PublicationError("batch journal empty-generation flag is invalid")
        if (
            not isinstance(objects, list)
            or (not objects and not allow_empty)
        ):
            raise PublicationError("batch journal objects are invalid")
        if not isinstance(entries, list):
            raise PublicationError("batch journal entries are invalid")
        if not isinstance(removed_objects, list):
            raise PublicationError("batch journal removed objects are invalid")
        if not objects and not removed_objects:
            raise PublicationError("empty generation must retire existing objects")

        destinations_by_object: dict[tuple[str, str], dict[str, Path]] = {}
        for item in objects:
            if not isinstance(item, dict):
                raise PublicationError("batch journal object is invalid")
            object_id = self._validate_object_id(item.get("id"))
            object_type = item.get("type")
            if object_type not in _TYPE_DIRECTORIES:
                raise PublicationError("batch journal object type is invalid")
            identity = (object_id, object_type)
            if identity in destinations_by_object:
                raise PublicationError("batch journal object is duplicated")
            destinations_by_object[identity] = self._destinations(
                object_id, object_type
            )

        removed_destinations: dict[
            tuple[str, str], dict[str, Path]
        ] = {}
        for item in removed_objects:
            if not isinstance(item, dict):
                raise PublicationError("batch journal removed object is invalid")
            object_id = self._validate_object_id(item.get("id"))
            object_type = item.get("type")
            if object_type not in _TYPE_DIRECTORIES:
                raise PublicationError(
                    "batch journal removed object type is invalid"
                )
            identity = (object_id, object_type)
            if (
                identity in removed_destinations
                or identity in destinations_by_object
            ):
                raise PublicationError(
                    "batch journal removed object is duplicated"
                )
            removed_destinations[identity] = self._destinations(
                object_id, object_type
            )

        expected_actions = {
            (object_id, object_type, kind): {"replace"}
            for object_id, object_type in destinations_by_object
            for kind in ("canonical", "card", "wiki")
        }
        for object_id, object_type in destinations_by_object:
            expected_actions[(object_id, object_type, "card")] = {
                "replace", "delete"
            }
        expected_actions.update(
            {
                (object_id, object_type, kind): {"delete"}
                for object_id, object_type in removed_destinations
                for kind in ("canonical", "card", "wiki")
            }
        )
        expected_actions[(None, None, "manifest")] = {"replace"}
        if len(entries) != len(expected_actions):
            raise PublicationError("batch journal entry count is invalid")

        normalized: list[tuple[dict[str, Any], Path]] = []
        seen_names: set[str] = set()
        seen_keys: set[tuple[str | None, str | None, str]] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise PublicationError("batch journal entry is invalid")
            name = entry.get("name")
            kind = entry.get("kind")
            if not isinstance(name, str) or not _GENERATION.fullmatch(name):
                raise PublicationError("batch journal entry name is invalid")
            if name in seen_names:
                raise PublicationError("batch journal entry name is duplicated")
            seen_names.add(name)
            object_id = entry.get("object_id")
            object_type = entry.get("object_type")
            key = (object_id, object_type, kind)
            if key not in expected_actions or key in seen_keys:
                raise PublicationError("batch journal entry identity is invalid")
            action = entry.get("action")
            if action not in expected_actions[key]:
                raise PublicationError("batch journal entry action is invalid")
            seen_keys.add(key)
            if kind == "manifest":
                if name != "manifest":
                    raise PublicationError("batch manifest entry is invalid")
                destination = self.knowledge_root / "manifest.yaml"
            else:
                identity = (object_id, object_type)
                destination_map = (
                    destinations_by_object
                    if (object_id, object_type) in destinations_by_object
                    else removed_destinations
                )
                destination = destination_map[identity][kind]
            if entry.get("destination") != str(
                destination.relative_to(self.knowledge_root)
            ):
                raise PublicationError(
                    "batch journal destination escaped root"
                )
            expected_staged = f"stage/{name}" if action == "replace" else None
            if entry.get("staged") != expected_staged:
                raise PublicationError(
                    "batch journal staged path escaped root"
                )
            if entry.get("backup") != f"backup/{name}":
                raise PublicationError("batch journal backup escaped root")
            normalized.append((entry, destination))
        if seen_keys != set(expected_actions):
            raise PublicationError("batch journal entries are incomplete")

        if self._manifest_generation() == generation:
            self._remove_transaction(transaction)
            return

        normalized.sort(key=lambda item: item[0]["kind"] == "manifest")
        for entry, destination in normalized:
            self._ensure_managed_parent(destination.parent)
            name = entry["name"]
            kind = entry["kind"]
            if entry.get("had_destination") is True:
                data = self._read_regular(transaction / "backup" / name)
                restore = transaction / f"restore-{name}"
                if self._lexists(restore):
                    self._unlink_file(restore)
                self._write_bytes(
                    restore, data, f"recovery.{kind}.stage"
                )
                self._inject(f"recovery.{kind}.replace")
                os.replace(restore, destination)
            elif entry.get("had_destination") is False:
                if self._lexists(destination):
                    self._unlink_file(destination)
            else:
                raise PublicationError(
                    "batch journal backup flag is invalid"
                )
            self._fsync_directory(
                destination.parent,
                f"recovery.{kind}.directory.fsync",
            )
        self._remove_transaction(transaction)

    def _destinations(
        self, module_id: str, object_type: str = "module"
    ) -> dict[str, Path]:
        type_directory = _TYPE_DIRECTORIES.get(object_type, "modules")
        result = {
            name: self.knowledge_root / directory / f"{module_id}{suffix}"
            for name, directory, suffix in _OUTPUTS
        }
        result["canonical"] = (
            self.knowledge_root / "objects" / type_directory / f"{module_id}.yaml"
        )
        result["manifest"] = self.knowledge_root / "manifest.yaml"
        return result

    def _safe_object_id(self, module: ModuleKnowledge) -> str:
        try:
            return self._validate_object_id(module.id)
        except Exception as error:
            raise PublicationError(f"unsafe module object id: {error}") from error

    @staticmethod
    def _validate_object_id(value: object) -> str:
        if not isinstance(value, str) or not _GENERATION.fullmatch(value):
            raise PublicationError("object id contains unsafe path characters")
        return value

    @staticmethod
    def _validate_generation(generation: object) -> None:
        if (
            not isinstance(generation, str)
            or generation in {".", ".."}
            or not _GENERATION.fullmatch(generation)
        ):
            raise PublicationError("generation contains unsafe path characters")

    def _assert_safe_roots(self, *, create: bool) -> None:
        self._reject_symlink_ancestry(self.output_root)
        if self.output_root.is_symlink():
            raise PublicationError("output root must not be a symlink")
        if create:
            self._mkdir(self.output_root)
            self._mkdir(self.knowledge_root)
            self._mkdir(self.knowledge_root / "state")
            self._mkdir(self.transactions_root)
        else:
            if self.knowledge_root.is_symlink():
                raise PublicationError(".knowledge root must not be a symlink")
            current = self.knowledge_root
            for part in ("state", "transactions"):
                current = current / part
                if self._lexists(current) and (
                    current.is_symlink() or not current.is_dir()
                ):
                    raise PublicationError(
                        "transaction path must not be a symlink or "
                        f"non-directory: {current}"
                    )
        if self.knowledge_root.exists() and not self.knowledge_root.is_dir():
            raise PublicationError(".knowledge root is not a directory")

    @staticmethod
    def _reject_symlink_ancestry(path: Path) -> None:
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current = current / part
            if os.path.lexists(current) and current.is_symlink():
                raise PublicationError(
                    f"output root ancestry contains a symlink: {current}"
                )

    @staticmethod
    def _mkdir(path: Path) -> None:
        if path.is_symlink():
            raise PublicationError(f"managed directory is a symlink: {path}")
        try:
            path.mkdir(exist_ok=True)
        except FileNotFoundError:
            path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise PublicationError(f"managed path is not a safe directory: {path}")

    def _ensure_managed_parent(self, path: Path) -> None:
        try:
            path.relative_to(self.knowledge_root)
        except ValueError as error:
            raise PublicationError("managed destination escaped .knowledge") from error
        current = self.knowledge_root
        for part in path.relative_to(self.knowledge_root).parts:
            current = current / part
            self._mkdir(current)

    def _write_bytes(self, path: Path, data: bytes, point: str) -> None:
        if self._lexists(path):
            raise PublicationError(f"staging file already exists: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                self._inject(f"{point}.write")
                stream.write(data)
                self._inject(f"{point}.flush")
                stream.flush()
                self._inject(f"{point}.fsync")
                os.fsync(stream.fileno())
        finally:
            os.close(fd)

    def _read_regular(self, path: Path) -> bytes:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise PublicationError(f"managed file is not regular: {path}")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read()
        finally:
            os.close(fd)

    def _fsync_directory(self, path: Path, point: str) -> None:
        self._inject(point)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _manifest_generation(self) -> str | None:
        value = self._manifest_value("active_generation")
        return value if isinstance(value, str) else None

    def _manifest_value(self, field: str) -> object | None:
        path = self.knowledge_root / "manifest.yaml"
        if not self._lexists(path):
            return None
        try:
            value = yaml.safe_load(self._read_regular(path))
        except (ValueError, yaml.YAMLError):
            return None
        except OSError as error:
            if error.errno == errno.ENOENT:
                return None
            raise PublicationError(f"manifest is unreadable: {error}") from error
        return value.get(field) if isinstance(value, dict) else None

    def _manifest_objects(self) -> tuple[tuple[str, str], ...]:
        path = self.knowledge_root / "manifest.yaml"
        if not self._lexists(path):
            return ()
        try:
            value = yaml.safe_load(self._read_regular(path))
        except (ValueError, yaml.YAMLError):
            return ()
        except OSError as error:
            if error.errno == errno.ENOENT:
                return ()
            raise PublicationError(f"manifest is unreadable: {error}") from error
        if not isinstance(value, dict) or "objects" not in value:
            return ()
        objects = value["objects"]
        if not isinstance(objects, list):
            raise PublicationError("manifest object inventory is invalid")
        identities: set[tuple[str, str]] = set()
        for item in objects:
            if not isinstance(item, dict):
                raise PublicationError("manifest object inventory is invalid")
            object_id = self._validate_object_id(item.get("id"))
            object_type = item.get("type")
            if object_type not in _TYPE_DIRECTORIES:
                raise PublicationError("manifest object type is invalid")
            identity = (object_id, object_type)
            if identity in identities:
                raise PublicationError("manifest object inventory is duplicated")
            identities.add(identity)
        return tuple(sorted(identities))

    @staticmethod
    def _lexists(path: Path) -> bool:
        return os.path.lexists(path)

    @staticmethod
    def _unlink_file(path: Path) -> None:
        if path.is_dir() and not path.is_symlink():
            raise PublicationError(f"refusing to unlink managed directory: {path}")
        path.unlink(missing_ok=True)

    def _remove_transaction(self, transaction: Path) -> None:
        if transaction.parent != self.transactions_root or transaction.is_symlink():
            raise PublicationError("refusing to remove unsafe transaction path")
        if transaction.exists():
            shutil.rmtree(transaction)
            self._fsync_directory(
                self.transactions_root, "cleanup.transactions.directory.fsync"
            )


__all__ = [
    "GenerationPublisher",
    "PublicationError",
    "PublishedGeneration",
    "PublishedGenerationBatch",
    "PublishedObject",
]
