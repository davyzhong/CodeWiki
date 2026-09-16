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
        assert b"knowledge catalog" in index.read()

        detail = _request(
            server, "/architecture/architecture.knowledge.html"
        )
        if detail.status == 200:
            assert b"<!doctype html>" in detail.read().lower()

        wiki = _request(server, "/repo-wiki.html")
        assert wiki.status == 200
        assert b"<!doctype html>" in wiki.read().lower()

        for path in (
            "/../manifest.yaml",
            "/objects",
            "/config.yaml",
            "/../../etc/hosts",
            "/site/../manifest.yaml",
        ):
            blocked = _request(server, path)
            assert blocked.status == 404
            blocked.read()
    finally:
        server.shutdown()
        server.server_close()


def test_falls_back_to_single_file_when_site_missing(tmp_path: Path) -> None:
    import shutil

    compiled_store(tmp_path)
    shutil.rmtree(tmp_path / ".knowledge/exports/site")
    server = create_wiki_server(tmp_path, port=0)
    server.timeout = 0.2
    runner = threading.Thread(target=server.serve_forever, daemon=True)
    runner.start()
    try:
        index = _request(server, "/")
        assert index.status == 200
        assert b"repo-wiki.html" in index.read()

        site_page = _request(server, "/sources.html")
        assert site_page.status == 404
        site_page.read()
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


def _retrieval_world(tmp_path: Path) -> Path:
    sys.path.insert(0, str(ROOT / "tests/retrieval"))
    from test_context_retrieval import (
        make_repo,
        publish_verified_world,
    )
    from knowledge_compiler.compiler.wiki import compile_repository_wiki
    from knowledge_compiler.retrieval.context import build_knowledge_index

    repo = make_repo(tmp_path)
    publish_verified_world(repo)
    build_knowledge_index(repo)
    compile_repository_wiki(repo)
    return repo


def test_preview_endpoint_serves_task_context(tmp_path: Path) -> None:
    repo = _retrieval_world(tmp_path)
    server = create_wiki_server(repo, port=0)
    server.timeout = 0.2
    runner = threading.Thread(target=server.serve_forever, daemon=True)
    runner.start()
    try:
        ok = _request(server, "/api/preview?task=checkout")
        assert ok.status == 200
        body = ok.read()
        assert b'"markdown"' in body

        empty = _request(server, "/api/preview?task=")
        assert empty.status == 400

        too_long = _request(
            server, "/api/preview?task=" + "x" * 501
        )
        assert too_long.status == 400

        missing = _request(server, "/api/preview")
        assert missing.status == 400
    finally:
        server.shutdown()
        server.server_close()


def test_preview_endpoint_fails_closed_without_index(tmp_path: Path) -> None:
    compiled_store(tmp_path)
    server = create_wiki_server(tmp_path, port=0)
    server.timeout = 0.2
    runner = threading.Thread(target=server.serve_forever, daemon=True)
    runner.start()
    try:
        response = _request(server, "/api/preview?task=checkout")
        assert response.status == 503
        assert b'"error"' in response.read()
    finally:
        server.shutdown()
        server.server_close()
