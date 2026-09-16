from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit


_ALLOWED_ROOT_PATHS = ("/", "/index.html")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
}


class ServeError(RuntimeError):
    """Raised when the local knowledge server cannot start safely."""


def _site_file(site_root: Path, request_path: str) -> Path | None:
    """Resolve a request path to a regular file inside the site root.

    Only ``.html`` files are served; traversal, symlinks, and any file
    outside the compiled site directory are rejected with 404.
    """

    relative = request_path.lstrip("/")
    if not relative or not relative.endswith(".html"):
        return None
    candidate = (site_root / relative).resolve()
    if candidate.suffix not in _CONTENT_TYPES:
        return None
    if not candidate.is_relative_to(site_root):
        return None
    if candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def _make_handler(
    payload: bytes, site_root: Path | None = None
) -> type[BaseHTTPRequestHandler]:
    class WikiHandler(BaseHTTPRequestHandler):
        server_version = "KnowledgeServe/0.1"
        sys_version = ""

        def do_GET(self) -> None:  # noqa: N802
            self._serve(head_only=False)

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve(head_only=True)

        def _serve(self, *, head_only: bool) -> None:
            path = urlsplit(self.path).path
            body: bytes | None = None
            content_type = "text/html; charset=utf-8"
            if path in _ALLOWED_ROOT_PATHS and site_root is not None:
                candidate = _site_file(site_root, "index.html")
                if candidate is not None:
                    body = candidate.read_bytes()
            elif path in _ALLOWED_ROOT_PATHS:
                body = (
                    b"<!doctype html>\n"
                    b"<meta http-equiv=\"refresh\""
                    b" content=\"0; url=/repo-wiki.html\">\n"
                )
            elif path == "/repo-wiki.html":
                body = payload
            elif site_root is not None:
                candidate = _site_file(site_root, path)
                if candidate is not None:
                    body = candidate.read_bytes()
            if body is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
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

    The server prefers the compiled multi-page site under
    ``.knowledge/exports/site`` when present and falls back to the
    standalone single-file export otherwise. Only loopback binding is
    allowed so the Wiki never leaks to the network.
    """

    root = Path(repository_root).resolve()
    html_path = root / ".knowledge/exports/repo-wiki.html"
    if not html_path.is_file():
        raise ServeError("compiled HTML Wiki not found; run knowledge compile")
    if html_path.is_symlink() or not html_path.is_file():
        raise ServeError("compiled HTML Wiki is not a regular file")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ServeError("the knowledge server only binds to loopback")
    site_root = (root / ".knowledge/exports/site").resolve()
    if not (site_root / "index.html").is_file() or site_root.is_symlink():
        site_root = None
    payload = html_path.read_bytes()
    return HTTPServer((host, port), _make_handler(payload, site_root))


__all__ = ["ServeError", "create_wiki_server"]
