from __future__ import annotations

import html as _html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from knowledge_compiler.compiler.human import (
    render_overlay_field,
    render_overlay_notes,
)
from knowledge_compiler.compiler.markdown import _code, _text
from knowledge_compiler.compiler.mermaid import (
    compile_architecture_graph,
    compile_flow_sequence,
)
from knowledge_compiler.compiler.typed_views import compile_typed_wiki


class WikiCompilationError(RuntimeError):
    """Raised when deterministic Wiki compilation cannot complete safely."""


@dataclass(frozen=True)
class WikiCompilationResult:
    generation: str
    pages: tuple[str, ...]
    html_path: Path
    stale_object_ids: tuple[str, ...]
    orphaned_overlay_ids: tuple[str, ...]


_TYPE_DIRECTORIES = {
    "module": "modules",
    "architecture": "architecture",
    "flow": "flows",
    "rule": "rules",
    "tech-stack": "tech-stack",
}


def compile_repository_wiki(
    repository_root: Path,
) -> WikiCompilationResult:
    """Compile the complete deterministic Wiki and standalone HTML.

    Reads only committed canonical state: the manifest-bound object set
    with its Evidence Packs, active human overlays, and retired overlay
    archives. Writes every Wiki page, the HTML export, and stamps
    ``wiki_generation`` in the manifest last. A failure leaves the
    previous stamp untouched so readers can detect the lag.
    """

    from knowledge_compiler.human.overlays import load_active_overlays
    from knowledge_compiler.incremental.invalidation import (
        load_generation_knowledge,
    )

    root = Path(repository_root).resolve()
    try:
        objects, packs = _load_compile_inputs(root)
        overlays = load_active_overlays(root)
        manifest_path = root / ".knowledge/manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_bytes())
        if not isinstance(manifest, dict):
            raise ValueError("manifest is invalid")
        active = manifest.get("active_generation")
        if not isinstance(active, str):
            raise ValueError("manifest has no active generation")
    except Exception as error:
        if isinstance(error, WikiCompilationError):
            raise
        raise WikiCompilationError(f"wiki inputs are unreadable: {error}") from error

    orphans = _orphaned_overlay_ids(root, objects)
    stale_ids = tuple(
        sorted(
            object_id
            for object_id, canonical in objects.items()
            if canonical.validity.status == "stale"
        )
    )

    pages: dict[str, bytes] = {}
    for object_id, canonical in sorted(objects.items()):
        pages[f"{_TYPE_DIRECTORIES[canonical.type]}/{object_id}.md"] = (
            _object_page(
                canonical,
                packs.get(object_id),
                overlays.get(object_id),
                root,
            )
        )
    pages["index.md"] = _index_page(root, objects, active, stale_ids, orphans)
    pages["architecture.md"] = _architecture_page(objects, overlays)
    pages["rules.md"] = _rules_page(objects, overlays)
    pages["tech-stack.md"] = _tech_stack_page(objects, overlays)
    pages["sources.md"] = _sources_page(root, objects, packs)

    html_bytes = _standalone_html(
        root, active, stale_ids, orphans, pages, objects, packs, overlays
    )

    knowledge_root = root / ".knowledge"
    try:
        for relative, data in sorted(pages.items()):
            destination = knowledge_root / "views/wiki" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        html_path = knowledge_root / "exports/repo-wiki.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_bytes(html_bytes)
        _stamp_wiki_generation(manifest_path, manifest, active)
    except OSError as error:
        raise WikiCompilationError(f"wiki output write failed: {error}") from error

    return WikiCompilationResult(
        generation=active,
        pages=tuple(sorted(pages)),
        html_path=html_path,
        stale_object_ids=stale_ids,
        orphaned_overlay_ids=orphans,
    )


def _load_compile_inputs(
    root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Load the manifest-bound set, tolerating inventory-less manifests.

    The legacy single-object publication writes no ``objects`` inventory;
    for those stores the compiler discovers canonical files on disk so
    human views still compile. A manifest that claims an inventory but
    cannot back it still fails closed.
    """

    from knowledge_compiler.incremental.invalidation import (
        InvalidationError,
        load_generation_knowledge,
    )

    try:
        return load_generation_knowledge(root)
    except InvalidationError:
        manifest_path = root / ".knowledge/manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_bytes())
        if isinstance(manifest, dict) and "objects" in manifest:
            raise
        return _discover_objects(root), {}


def _discover_objects(root: Path) -> dict[str, object]:
    from knowledge_compiler.contracts.canonical import (
        parse_canonical_knowledge,
    )
    from knowledge_compiler.human.overlays import DIRECTORY_TYPES

    objects: dict[str, object] = {}
    objects_root = root / ".knowledge/objects"
    if not objects_root.is_dir():
        return objects
    for path in sorted(objects_root.glob("*/*.yaml")):
        object_type = DIRECTORY_TYPES.get(path.parent.name)
        if object_type is None or path.is_symlink() or not path.is_file():
            continue
        payload = yaml.safe_load(path.read_bytes())
        canonical = parse_canonical_knowledge(payload)
        if canonical.type != object_type or canonical.id != path.stem:
            continue
        objects[canonical.id] = canonical
    return objects


def _object_page(
    canonical: object,
    pack: object | None,
    overlay: object | None,
    root: Path,
) -> bytes:
    from knowledge_compiler.compiler.markdown import compile_module_wiki

    if (
        canonical.type == "module"
        and pack is not None
        and canonical.validity.status == "verified"
    ):
        body = compile_module_wiki(canonical, pack, overlay)
    else:
        # A stale module or one without a persisted Evidence Pack still
        # deserves a readable page; the generic renderer never invents
        # claims and the stale banner is prepended below.
        body = compile_typed_wiki(canonical, overlay)
    validity = canonical.validity
    if validity.status != "stale":
        return body
    lines = [
        "> [!WARNING] Stale knowledge — expiry warning",
        ">",
        f"> - status: `{validity.status}`",
        f"> - reason: {_text(validity.stale_reason or 'unknown')}",
        f"> - last verified commit: {_code(validity.verified_commit)}",
        "> - This page lags the repository; run `knowledge update`.",
        "",
    ]
    return b"".join([("\n".join(lines) + "\n").encode("utf-8"), body])


def _index_page(
    root: Path,
    objects: dict[str, object],
    active: str,
    stale_ids: tuple[str, ...],
    orphans: tuple[str, ...],
) -> bytes:
    lines = [
        f"# {root.name} knowledge wiki",
        "",
        f"- active generation: {_code(active)}",
        f"- objects: {len(objects)}",
        "- source index: [sources.md](sources.md)",
        "",
        "## Catalog",
        "",
    ]
    grouped: dict[str, list[str]] = {}
    for object_id, canonical in sorted(objects.items()):
        grouped.setdefault(canonical.type, []).append(object_id)
    aggregate = {
        "architecture": "architecture.md",
        "rule": "rules.md",
        "tech-stack": "tech-stack.md",
    }
    for type_name in sorted(grouped):
        ids = grouped[type_name]
        lines.append(f"- {type_name} ({len(ids)})")
        if type_name in aggregate:
            lines.append(f"  - aggregate page: [{aggregate[type_name]}]({aggregate[type_name]})")
        for object_id in ids:
            marker = " · stale" if object_id in stale_ids else ""
            lines.append(
                f"  - [{_text(object_id)}]"
                f"({_TYPE_DIRECTORIES[type_name]}/{object_id}.md){marker}"
            )
    if orphans:
        lines.extend(
            [
                "",
                "## Orphaned human knowledge",
                "",
                "> [!WARNING] Archived overlays below have no live object.",
                "",
            ]
        )
        lines.extend(f"- {_text(object_id)} (archived)" for object_id in orphans)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _architecture_page(
    objects: dict[str, object], overlays: dict[str, object]
) -> bytes:
    lines = ["# Architecture", ""]
    architectures = sorted(
        (c for c in objects.values() if c.type == "architecture"),
        key=lambda c: c.id,
    )
    if not architectures:
        lines.append("_No architecture knowledge is published._")
        return ("\n".join(lines) + "\n").encode("utf-8")
    for canonical in architectures:
        overlay = overlays.get(canonical.id)
        lines.extend(
            [
                f"## {_text(canonical.title)}",
                "",
                f"- id: {_code(canonical.id)}",
                "",
            ]
        )
        lines.extend(
            render_overlay_field(
                [_text(canonical.summary.text)],
                overlay=overlay,
                field="summary",
                escape=_text,
            )
        )
        graph = compile_architecture_graph(canonical).decode("utf-8").rstrip("\n")
        lines.extend(["", "```mermaid", graph, "```"])
        lines.extend(["", "### Components", ""])
        for component in canonical.components:
            lines.append(
                f"- **{_text(component.name)}** — {_text(component.responsibility)}"
            )
        if canonical.boundaries:
            lines.extend(["", "### Boundaries", ""])
            for boundary in canonical.boundaries:
                lines.append(
                    f"- **{_text(boundary.name)}** — {_text(boundary.description)}"
                )
        lines.extend(["", "### Relationships", ""])
        for relationship in canonical.relationships:
            lines.append(
                f"- {_text(relationship.source)} "
                f"{_text(relationship.predicate)} "
                f"{_text(relationship.target)}"
            )
        lines.extend(render_overlay_notes(overlay, escape=_text))
        lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _rules_page(objects: dict[str, object], overlays: dict[str, object]) -> bytes:
    lines = ["# Rules", ""]
    rules = sorted(
        (c for c in objects.values() if c.type == "rule"),
        key=lambda c: c.id,
    )
    if not rules:
        lines.append("_No rule knowledge is published._")
        return ("\n".join(lines) + "\n").encode("utf-8")
    for canonical in rules:
        overlay = overlays.get(canonical.id)
        lines.extend(
            [
                f"## {_text(canonical.title)}",
                "",
                f"- id: {_code(canonical.id)}",
                f"- severity: **{canonical.severity}**",
                "",
            ]
        )
        lines.extend(
            render_overlay_field(
                [_text(canonical.statement.text)],
                overlay=overlay,
                field="statement",
                escape=_text,
            )
        )
        lines.extend(["", "### Applicability", ""])
        lines.extend(f"- {_code(path)}" for path in canonical.applicability.paths)
        if canonical.constraints:
            lines.extend(["", "### Constraints", ""])
            for constraint in canonical.constraints:
                lines.append(f"- {_text(constraint.description)}")
        if canonical.exceptions:
            lines.extend(["", "### Exceptions", ""])
            for exception in canonical.exceptions:
                lines.append(f"- {_text(exception.description)}")
        if canonical.related_objects:
            lines.extend(["", "### Related objects", ""])
            lines.extend(f"- {_code(item)}" for item in canonical.related_objects)
        lines.extend(render_overlay_notes(overlay, escape=_text))
        lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _tech_stack_page(
    objects: dict[str, object], overlays: dict[str, object]
) -> bytes:
    lines = ["# Tech stack", ""]
    stacks = sorted(
        (c for c in objects.values() if c.type == "tech-stack"),
        key=lambda c: c.id,
    )
    if not stacks:
        lines.append("_No tech-stack knowledge is published._")
        return ("\n".join(lines) + "\n").encode("utf-8")
    for canonical in stacks:
        overlay = overlays.get(canonical.id)
        lines.extend([f"## {_text(canonical.title)}", "", f"- id: {_code(canonical.id)}", ""])
        lines.extend(
            render_overlay_field(
                [_text(canonical.summary.text)],
                overlay=overlay,
                field="summary",
                escape=_text,
            )
        )
        lines.extend(["", "### Entries", ""])
        for entry in canonical.entries:
            lines.append(
                f"- **{_text(entry.name)}** — {_text(entry.category)} · "
                f"version {_code(entry.version)} · {_text(entry.scope)}"
            )
        if canonical.configurations:
            lines.extend(["", "### Configurations", ""])
            for configuration in canonical.configurations:
                lines.append(
                    f"- {_code(configuration.path)} — "
                    f"{_text(configuration.description)}"
                )
        lines.extend(render_overlay_notes(overlay, escape=_text))
        lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _sources_page(
    root: Path,
    objects: dict[str, object],
    packs: dict[str, object],
) -> bytes:
    del root
    lines = ["# Source index", ""]
    citations: dict[str, set[str]] = {}
    for object_id, canonical in objects.items():
        for claim in canonical.claims:
            for evidence_id in claim.evidence_ids:
                citations.setdefault(evidence_id, set()).add(object_id)
    by_path: dict[str, list[object]] = {}
    for object_id in sorted(packs):
        for item in packs[object_id].evidence:
            by_path.setdefault(item.path, []).append(item)
    if not by_path:
        lines.append("_No evidence sources are recorded._")
        return ("\n".join(lines) + "\n").encode("utf-8")
    for path in sorted(by_path):
        lines.extend([f"## {_text(path)}", ""])
        for item in sorted(
            by_path[path], key=lambda e: (e.start_line, e.end_line, e.id)
        ):
            symbol = f" · {_code(item.symbol)}" if item.symbol else ""
            cited = ", ".join(sorted(citations.get(item.id, ()))) or "uncited"
            lines.append(
                f"- L{item.start_line}-L{item.end_line}{symbol} · "
                f"commit {_code(item.commit[:12])} · cited by {_text(cited)}"
            )
        lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _orphaned_overlay_ids(
    root: Path, objects: dict[str, object]
) -> tuple[str, ...]:
    archive_root = root / ".knowledge/human/archive"
    if not archive_root.is_dir():
        return ()
    orphans: list[str] = []
    for path in sorted(archive_root.rglob("*.yaml")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(archive_root)
        if len(relative.parts) != 2:
            continue
        object_id = relative.stem
        if object_id in objects:
            continue
        expected_directory = _TYPE_DIRECTORIES.get(
            object_id.split(".", 1)[0]
        )
        if expected_directory is None or relative.parts[0] != expected_directory:
            continue
        orphans.append(object_id)
    return tuple(sorted(orphans))


def _stamp_wiki_generation(
    manifest_path: Path, manifest: dict, active: str
) -> None:
    manifest["wiki_generation"] = active
    data = yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
    temporary = manifest_path.with_name("manifest.yaml.tmp")
    temporary.write_bytes(data.encode("utf-8"))
    os.replace(temporary, manifest_path)


def _h(value: object) -> str:
    return _html.escape(str(value), quote=True)


def _standalone_html(
    root: Path,
    active: str,
    stale_ids: tuple[str, ...],
    orphans: tuple[str, ...],
    pages: dict[str, bytes],
    objects: dict[str, object],
    packs: dict[str, object],
    overlays: dict[str, object],
) -> bytes:
    from knowledge_compiler.compiler.mermaid import (
        render_architecture_graph_svg,
        render_flow_sequence_svg,
    )

    diagram_svgs: dict[str, bytes] = {}
    for canonical in objects.values():
        if canonical.type == "architecture":
            diagram_svgs[
                compile_architecture_graph(canonical).decode("utf-8").rstrip("\n")
            ] = render_architecture_graph_svg(canonical)
        elif canonical.type == "flow":
            diagram_svgs[
                compile_flow_sequence(canonical).decode("utf-8").rstrip("\n")
            ] = render_flow_sequence_svg(canonical)
    del packs, overlays
    freshness = "current" if not stale_ids else "stale-content"
    sections: list[str] = []
    search_index: list[dict[str, str]] = []
    for relative in sorted(pages):
        markdown = pages[relative].decode("utf-8")
        body = _markdown_to_html(markdown, diagram_svgs)
        anchor = re.sub(r"[^a-z0-9]+", "-", relative.lower()).strip("-")
        sections.append(
            f'<section id="page-{_h(anchor)}" data-page="{_h(relative)}">'
            f"<h2>{_h(relative)}</h2>\n{body}</section>"
        )
        text = re.sub(r"<[^>]+>", " ", body)
        search_index.append(
            {
                "id": anchor,
                "title": relative,
                "text": re.sub(r"\s+", " ", text).strip()[:4000],
            }
        )
    catalog = "\n".join(
        f'<a href="#page-{re.sub(r"[^a-z0-9]+", "-", relative.lower()).strip("-")}">'
        f"{_h(relative)}</a>"
        for relative in sorted(pages)
    )
    payload = json.dumps(search_index, ensure_ascii=False, sort_keys=True)
    commit = _representative_commit(objects)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_h(root.name)} knowledge wiki</title>\n"
        "<style>\n"
        "body{font-family:sans-serif;margin:0;display:flex}\n"
        "nav{width:240px;background:#f6f8fa;padding:16px;position:sticky;top:0;"
        "height:100vh;overflow:auto;box-sizing:border-box}\n"
        "nav a{display:block;padding:2px 0}\n"
        "main{flex:1;padding:24px;max-width:900px}\n"
        ".stale{background:#fff3cd;border-left:4px solid #d97706;padding:8px 12px}\n"
        "details{margin:4px 0}\n"
        "pre{background:#f6f8fa;padding:8px;overflow:auto}\n"
        ".diagram{border:1px solid #d0d7de;border-radius:6px;margin:8px 0}\n"
        "</style>\n</head>\n<body>\n"
        f"<nav><h3>{_h(root.name)}</h3>\n"
        f"<p>generation: {_h(active)}<br>freshness: {_h(freshness)}<br>"
        f"commit: {_h(commit)}</p>\n"
        '<input id="search" type="search" placeholder="Search wiki"'
        ' oninput="filter()">\n'
        f'<div id="catalog">{catalog}</div></nav>\n'
        "<main>\n"
        + (
            '<p class="stale">Stale objects are present; content may lag the'
            " repository. Run knowledge update.</p>\n"
            if stale_ids
            else ""
        )
        + (
            '<p class="stale">Orphaned human knowledge: '
            + _h(", ".join(orphans))
            + "</p>\n"
            if orphans
            else ""
        )
        + "\n".join(sections)
        + "\n</main>\n<script>\nvar INDEX="
        + payload
        + ";\n"
        "function filter(){var q=document.getElementById('search').value."
        "toLowerCase();var seen={};INDEX.forEach(function(item){"
        "seen[item.id]=!q||item.text.toLowerCase().indexOf(q)>=0||"
        "item.title.toLowerCase().indexOf(q)>=0;});"
        "document.querySelectorAll('main section').forEach(function(s){"
        "var id=s.id.replace('page-','');"
        "s.style.display=seen[id]===false?'none':'';});}\n"
        "</script>\n</body>\n</html>\n"
    ).encode("utf-8")


def _representative_commit(objects: dict[str, object]) -> str:
    commits = sorted(
        {
            canonical.validity.verified_commit
            for canonical in objects.values()
        }
    )
    return commits[0] if commits else "unknown"


_INLINE_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _inline_html(text: str) -> str:
    escaped = _h(text)
    escaped = _INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)
    escaped = _LINK.sub(
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', escaped
    )
    escaped = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", escaped)
    return escaped


def _markdown_to_html(
    markdown: str, diagram_svgs: dict[str, bytes] | None = None
) -> str:
    lines = markdown.split("\n")
    html_lines: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    quote_lines: list[str] = []
    code_lines: list[str] | None = None
    code_language = ""
    in_details = 0

    def flush_paragraph():
        if paragraph:
            html_lines.append(f"<p>{_inline_html(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list():
        if list_items:
            html_lines.append("<ul>" + "".join(list_items) + "</ul>")
            list_items.clear()

    def flush_quote():
        if quote_lines:
            body = _inline_html(" ".join(part.strip() for part in quote_lines))
            html_lines.append(f"<blockquote>{body}</blockquote>")
            quote_lines.clear()

    for raw in lines:
        line = raw.rstrip("\n")
        if code_lines is not None:
            if line.strip() == "```":
                source = "\n".join(code_lines)
                svg = (diagram_svgs or {}).get(source)
                if svg is not None:
                    html_lines.append(
                        '<div class="diagram">'
                        + svg.decode("utf-8").rstrip("\n")
                        + "</div>"
                    )
                else:
                    language_class = (
                        ' class="mermaid-src"'
                        if code_language == "mermaid"
                        else ""
                    )
                    html_lines.append(
                        f"<pre{language_class}><code>"
                        + _h(source)
                        + "</code></pre>"
                    )
                code_lines = None
            else:
                code_lines.append(line)
            continue
        stripped = line.strip()
        if stripped == "```":
            flush_paragraph()
            flush_list()
            flush_quote()
            code_lines = []
            code_language = ""
            continue
        if stripped.startswith("```") and len(stripped) > 3:
            flush_paragraph()
            flush_list()
            flush_quote()
            code_lines = []
            code_language = stripped[3:].strip()
            continue
        if not stripped:
            flush_paragraph()
            flush_list()
            flush_quote()
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            flush_quote()
            level = len(heading.group(1))
            html_lines.append(
                f"<h{level}>{_inline_html(heading.group(2))}</h{level}>"
            )
            continue
        if stripped == "<details>":
            flush_paragraph()
            flush_list()
            flush_quote()
            html_lines.append("<details>")
            in_details += 1
            continue
        if stripped == "</details>":
            flush_paragraph()
            flush_list()
            flush_quote()
            if in_details:
                html_lines.append("</details>")
                in_details -= 1
            continue
        summary = re.match(r"^<summary>(.*)</summary>$", stripped)
        if summary:
            html_lines.append(f"<summary>{_inline_html(summary.group(1))}</summary>")
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            flush_list()
            quote_lines.append(stripped.lstrip(">"))
            continue
        item = re.match(r"^\s*[-*]\s+(.*)$", raw)
        if item:
            flush_paragraph()
            flush_quote()
            list_items.append(f"<li>{_inline_html(item.group(1))}</li>")
            close_list = True
            continue
        flush_list()
        flush_quote()
        paragraph.append(stripped)
    flush_paragraph()
    flush_list()
    flush_quote()
    if code_lines is not None:
        raise WikiCompilationError("unterminated fenced code block")
    return "\n".join(html_lines)


__all__ = [
    "WikiCompilationError",
    "WikiCompilationResult",
    "compile_repository_wiki",
]
