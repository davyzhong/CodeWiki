from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit


_ALLOWED_PATHS = ("/", "/index.html", "/repo-wiki.html")


class ServeError(RuntimeError):
    """Raised when the local knowledge server cannot start safely."""


def _make_handler(payload: bytes) -> type[BaseHTTPRequestHandler]:
    class WikiHandler(BaseHTTPRequestHandler):
        server_version = "KnowledgeServe/0.1"
        sys_version = ""

        def do_GET(self) -> None:  # noqa: N802
            self._serve(head_only=False)

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve(head_only=True)

        def _serve(self, *, head_only: bool) -> None:
            path = urlsplit(self.path).path
            if path not in _ALLOWED_PATHS:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = (
                b"<!doctype html>\n"
                b"<meta http-equiv=\"refresh\""
                b" content=\"0; url=/repo-wiki.html\">\n"
                if path in ("/", "/index.html")
                else payload
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            # A quiet local server; request logging is not part of the
            # read-only contract.
            return

    return WikiHandler


def create_wiki_server(
    repository_root: Path, port: int = 8765, host: str = "127.0.0.1"
) -> HTTPServer:
    """Create a local-only, read-only server for the compiled Wiki.

    Exactly one document is served; every other path is a 404. The
    socket binds to loopback by default so the Wiki never leaks to the
    network.
    """

    root = Path(repository_root).resolve()
    html_path = root / ".knowledge/exports/repo-wiki.html"
    if not html_path.is_file():
        raise ServeError("compiled HTML Wiki not found; run knowledge compile")
    if html_path.is_symlink() or not html_path.is_file():
        raise ServeError("compiled HTML Wiki is not a regular file")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ServeError("the knowledge server only binds to loopback")
    payload = html_path.read_bytes()
    return HTTPServer((host, port), _make_handler(payload))


__all__ = ["ServeError", "create_wiki_server"]
