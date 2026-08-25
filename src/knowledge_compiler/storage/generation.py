from __future__ import annotations

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


_GENERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_OUTPUTS = (
    ("canonical", "objects/modules", ".yaml"),
    ("card", "views/cards", ".md"),
    ("wiki", "views/wiki", ".md"),
)


class PublicationError(RuntimeError):
    """Raised when a generation cannot be safely published or recovered."""


@dataclass(frozen=True)
class PublishedGeneration:
    generation: str
    canonical_path: Path
    card_path: Path
    wiki_path: Path
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
        evidence_pack: EvidencePack,
    ) -> PublishedGeneration:
        self._validate_generation(generation)
        try:
            # Compilation and contract revalidation must complete before the first
            # output-directory mutation.
            compiled = {
                "canonical": compile_module_yaml(module, evidence_pack),
                "card": compile_module_card(module, evidence_pack),
                "wiki": compile_module_wiki(module, evidence_pack),
            }
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
        destinations = self._destinations(module_id)
        transaction = self.transactions_root / generation
        # A generation id names one committed content set. Republishing the
        # same id with differing bytes would let a later recovery mistake a
        # partially replaced tree for a committed one, so reject the
        # ambiguity before the first mutation.
        if self._manifest_generation() == generation:
            for name, destination in destinations.items():
                if not self._lexists(destination) or self._read_regular(
                    destination
                ) != payloads[name]:
                    raise PublicationError(
                        "generation id reuse with differing content: " + name
                    )
        try:
            self._assert_safe_roots(create=True)
            if transaction.exists() or transaction.is_symlink():
                raise PublicationError(
                    f"generation transaction already exists: {generation}"
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

    def recover(self) -> None:
        """Recover every incomplete journal; safe to repeat after interruption."""

        try:
            self._assert_safe_roots(create=False)
            if not self.transactions_root.exists():
                return
            for transaction in sorted(self.transactions_root.iterdir()):
                if transaction.is_symlink() or not transaction.is_dir():
                    raise PublicationError("transaction entry is not a safe directory")
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
            if generation != transaction.name or journal.get("schema_version") != 1:
                raise PublicationError("transaction journal identity is invalid")
            module_id = journal["object_id"]
            expected = self._destinations(self._validate_object_id(module_id))
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

    def _destinations(self, module_id: str) -> dict[str, Path]:
        result = {
            name: self.knowledge_root / directory / f"{module_id}{suffix}"
            for name, directory, suffix in _OUTPUTS
        }
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
        elif self.knowledge_root.is_symlink():
            raise PublicationError(".knowledge root must not be a symlink")
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
        path = self.knowledge_root / "manifest.yaml"
        if not self._lexists(path):
            return None
        try:
            value = yaml.safe_load(self._read_regular(path))
        except (OSError, ValueError, yaml.YAMLError):
            return None
        return value.get("active_generation") if isinstance(value, dict) else None

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


__all__ = ["GenerationPublisher", "PublicationError", "PublishedGeneration"]
