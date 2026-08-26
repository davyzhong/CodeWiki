from __future__ import annotations

import http.client
import sys
import threading
from pathlib import Path

import pytest

from knowledge_compiler.serving import ServeError, create_wiki_server


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/integration"))

from test_typed_publication import canonicalize  # noqa: E402


def compiled_store(tmp_path: Path) -> Path:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki
    from knowledge_compiler.storage import GenerationPublisher

    architecture = canonicalize("architecture").canonical
    assert architecture is not None
    GenerationPublisher(tmp_path).publish_generation(
        "gen-serve-001", ((architecture, None),)
    )
    compile_repository_wiki(tmp_path)
    return tmp_path


def _request(server, path: str) -> http.client.HTTPResponse:
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(host, port, timeout=5)
    try:
        connection.request("GET", path)
        return connection.getresponse()
    finally:
        connection.close()


def test_serves_only_the_compiled_wiki_on_loopback(tmp_path: Path) -> None:
    compiled_store(tmp_path)
    server = create_wiki_server(tmp_path, port=0)
    server.timeout = 0.2
    runner = threading.Thread(target=server.serve_forever, daemon=True)
    runner.start()
    try:
        index = _request(server, "/")
        assert index.status == 200
        assert b"repo-wiki.html" in index.read()

        wiki = _request(server, "/repo-wiki.html")
        assert wiki.status == 200
        assert b"<!doctype html>" in wiki.read().lower()

        for path in ("/../manifest.yaml", "/objects", "/config.yaml"):
            blocked = _request(server, path)
            assert blocked.status == 404
            blocked.read()
    finally:
        server.shutdown()
        server.server_close()


def test_refuses_to_serve_without_compiled_html(tmp_path: Path) -> None:
    with pytest.raises(ServeError, match="HTML Wiki"):
        create_wiki_server(tmp_path, port=0)


def test_refuses_non_loopback_bind(tmp_path: Path) -> None:
    compiled_store(tmp_path)
    with pytest.raises(ServeError, match="loopback"):
        create_wiki_server(tmp_path, port=0, host="0.0.0.0")
