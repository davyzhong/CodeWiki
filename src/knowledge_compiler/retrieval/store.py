from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path


# Allowlist for FTS match terms: word characters only, so no quoting,
# operator, or filter syntax from task text can shape a query.
_WORD = re.compile(r"[\w]+")


class IndexStoreError(RuntimeError):
    """Raised when the FTS store cannot be written or read safely."""


def write_index(
    index_path: Path,
    meta_rows: list[tuple[str, str]],
    object_rows: list[tuple[str, str, str, str]],
    relation_rows: list[tuple[str, str, str]],
) -> None:
    """Atomically replace the index file with a complete projection.

    Every value travels as a bound parameter; the schema is a fixed
    constant. The temporary file is swapped into place only after the
    write committed, so readers never observe a partial index.
    """

    index_path = Path(index_path)
    temporary = index_path.with_name(index_path.name + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT); CREATE TABLE objects(object_id TEXT PRIMARY KEY, type TEXT, title TEXT); CREATE TABLE relations(object_id TEXT, target_id TEXT, predicate TEXT); CREATE VIRTUAL TABLE objects_fts USING fts5(object_id UNINDEXED, body);")
        connection.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", meta_rows)
        for object_id, object_type, title, body in object_rows:
            connection.execute("INSERT INTO objects(object_id, type, title) VALUES (?, ?, ?)", (object_id, object_type, title))
            connection.execute("INSERT INTO objects_fts(object_id, body) VALUES (?, ?)", (object_id, body))
        connection.executemany("INSERT INTO relations(object_id, target_id, predicate) VALUES (?, ?, ?)", relation_rows)
        connection.commit()
    except sqlite3.Error as error:
        raise IndexStoreError(f"index write failed: {error}") from error
    finally:
        connection.close()
    os.replace(temporary, index_path)


def read_meta(index_path: Path) -> dict[str, str]:
    connection = sqlite3.connect(Path(index_path))
    try:
        return dict(connection.execute("SELECT key, value FROM meta"))
    except sqlite3.Error as error:
        raise IndexStoreError(f"index read failed: {error}") from error
    finally:
        connection.close()


def search_terms(task: str) -> list[str]:
    return sorted({match.group(0) for match in _WORD.finditer(task)})


def match_objects(index_path: Path, task: str) -> dict[str, float]:
    """Return the best FTS rank per matched object.

    Terms are bare word-character strings bound as parameters, so task
    text can only select terms, never shape the query.
    """

    connection = sqlite3.connect(Path(index_path))
    try:
        ranks: dict[str, float] = {}
        for term in search_terms(task):
            for object_id, rank in connection.execute("SELECT object_id, rank FROM objects_fts WHERE objects_fts MATCH ? LIMIT 32", (term,)):
                ranks[object_id] = min(ranks.get(object_id, rank), rank)
        return ranks
    except sqlite3.Error as error:
        raise IndexStoreError(f"index search failed: {error}") from error
    finally:
        connection.close()


def relations_of(index_path: Path, object_id: str) -> list[tuple[str, str]]:
    connection = sqlite3.connect(Path(index_path))
    try:
        return list(connection.execute("SELECT target_id, predicate FROM relations WHERE object_id = ?", (object_id,)))
    except sqlite3.Error as error:
        raise IndexStoreError(f"index relation read failed: {error}") from error
    finally:
        connection.close()


__all__ = [
    "IndexStoreError",
    "match_objects",
    "read_meta",
    "relations_of",
    "search_terms",
    "write_index",
]
