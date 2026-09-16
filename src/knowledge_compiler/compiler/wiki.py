from __future__ import annotations

import html as _html
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from knowledge_compiler.compiler.human import (
    render_overlay_field,
    render_overlay_notes,
)
from knowledge_compiler.compiler.markdown import (
    _code,
    _evidence_permalink,
    _text,
)
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
    web_url = _load_web_url(root)

    pages: dict[str, bytes] = {}
    for object_id, canonical in sorted(objects.items()):
        pages[f"{_TYPE_DIRECTORIES[canonical.type]}/{object_id}.md"] = (
            _object_page(
                canonical,
                packs.get(object_id),
                overlays.get(object_id),
                root,
                web_url,
            )
        )
    pages["index.md"] = _index_page(root, objects, active, stale_ids, orphans)
    pages["architecture.md"] = _architecture_page(objects, overlays)
    pages["rules.md"] = _rules_page(objects, overlays)
    pages["tech-stack.md"] = _tech_stack_page(objects, overlays)
    pages["sources.md"] = _sources_page(root, objects, packs, web_url)

    diagram_svgs = _diagram_svgs(objects)
    rendered, search_index = _render_page_bodies(pages, diagram_svgs)
    insufficient = _insufficient_targets(root)
    html_bytes = _standalone_html(
        root,
        active,
        stale_ids,
        orphans,
        rendered,
        search_index,
        objects,
        packs,
        overlays,
        web_url,
        insufficient,
    )
    site_pages = _site_pages(
        root,
        active,
        stale_ids,
        orphans,
        rendered,
        search_index,
        objects,
        packs,
        insufficient,
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
        site_root = knowledge_root / "exports/site"
        shutil.rmtree(site_root, ignore_errors=True)
        for relative, data in sorted(site_pages.items()):
            destination = site_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
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


def _load_web_url(root: Path) -> str | None:
    """Read the optional repository web root for evidence permalinks.

    A missing or invalid config must not break Wiki compilation: the
    views degrade to plain citations without links.
    """

    from knowledge_compiler.config import load_config

    try:
        return load_config(root / ".knowledge/config.yaml").web_url
    except (OSError, ValueError):
        return None


def _object_page(
    canonical: object,
    pack: object | None,
    overlay: object | None,
    root: Path,
    web_url: str | None = None,
) -> bytes:
    from knowledge_compiler.compiler.markdown import compile_module_wiki

    if (
        canonical.type == "module"
        and pack is not None
        and canonical.validity.status == "verified"
    ):
        body = compile_module_wiki(canonical, pack, overlay, web_url=web_url)
    else:
        # A stale module or one without a persisted Evidence Pack still
        # deserves a readable page; the generic renderer never invents
        # claims and the stale banner is prepended below.
        body = compile_typed_wiki(
            canonical, overlay, pack=pack, web_url=web_url
        )
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
    web_url: str | None = None,
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
            location = f"L{item.start_line}-L{item.end_line}"
            permalink = _evidence_permalink(web_url, item)
            if permalink:
                location = f"[{location}]({permalink})"
            lines.append(
                f"- {location}{symbol} · "
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
    from knowledge_compiler.storage.lifecycle import (
        LifecycleWriteError,
        stamp_manifest_wiki_generation,
    )

    del manifest
    try:
        if not stamp_manifest_wiki_generation(manifest_path.parent, active):
            raise OSError("manifest disappeared before Wiki stamp")
    except LifecycleWriteError as error:
        raise OSError(f"Wiki manifest stamp failed: {error}") from error


def _h(value: object) -> str:
    return _html.escape(str(value), quote=True)


_TYPE_ORDER = ("architecture", "module", "flow", "rule", "tech-stack")

_PAGE_TYPE_DIRECTORIES = {value: key for key, value in _TYPE_DIRECTORIES.items()}


def _page_type(relative: str) -> str:
    head = relative.split("/", 1)[0]
    if head in _PAGE_TYPE_DIRECTORIES:
        return _PAGE_TYPE_DIRECTORIES[head]
    if relative == "architecture.md":
        return "architecture"
    if relative == "rules.md":
        return "rule"
    if relative == "tech-stack.md":
        return "tech-stack"
    return "overview"


def _insufficient_targets(
    root: Path,
) -> dict[str, tuple[int, list[str]]]:
    """Per-type insufficient_evidence terminal targets of the active run.

    The compile must never fail because run state is unreadable: the
    honesty layer degrades to empty counts instead.
    """

    runs_root = root / ".knowledge/state/runs"
    if not runs_root.is_dir():
        return {}
    try:
        from knowledge_compiler.orchestrator.contracts import TerminalResult
        from knowledge_compiler.orchestrator.store import RunStore

        records = RunStore(runs_root)._list_runs()
        record = next(
            (item for item in records if item.active),
            records[-1] if records else None,
        )
        if record is None:
            return {}
        counts: dict[str, tuple[int, list[str]]] = {}
        for target in record.targets:
            if target.result is not TerminalResult.INSUFFICIENT_EVIDENCE:
                continue
            type_name = target.target_id.split(".", 1)[0]
            count, ids = counts.get(type_name, (0, []))
            counts[type_name] = (count + 1, ids + [target.target_id])
        for type_name, (_count, ids) in counts.items():
            ids.sort()
        return counts
    except Exception:
        return {}


def _coverage_rows(
    objects: dict[str, object],
    insufficient: dict[str, tuple[int, list[str]]] | None = None,
) -> list[tuple[str, int, int, int]]:
    """Per-type published/stale/insufficient counts, honest about gaps."""

    insufficient = insufficient or {}
    rows: list[tuple[str, int, int, int]] = [
        (type_name, 0, 0, insufficient.get(type_name, (0, []))[0])
        for type_name in _TYPE_ORDER
    ]
    index = {type_name: position for position, (type_name, *_rest) in enumerate(rows)}
    for canonical in objects.values():
        if canonical.type not in index:
            continue
        type_name, published, stale, lacking = rows[index[canonical.type]]
        if canonical.validity.status == "stale":
            rows[index[canonical.type]] = (
                type_name, published, stale + 1, lacking,
            )
        else:
            rows[index[canonical.type]] = (
                type_name, published + 1, stale, lacking,
            )
    return rows


_WIKI_STYLE = """
:root{--bg:#ffffff;--fg:#1f2328;--muted:#59636e;--border:#d1d9e0;--sidebar:#f6f8fa;
--accent:#0969da;--green:#1a7f37;--yellow:#9a6700;--red:#cf222e;--code-bg:#f6f8fa;
--ok-bar:#1a7f37;--stale-bar:#bf8700}
[data-theme=dark]{--bg:#0d1117;--fg:#e6edf3;--muted:#8b949e;--border:#3d444d;
--sidebar:#161b22;--accent:#4493f8;--green:#3fb950;--yellow:#d29922;--red:#f85149;
--code-bg:#161b22;--ok-bar:#3fb950;--stale-bar:#d29922}
@media (prefers-color-scheme: dark){
:root:not([data-theme=light]):not([data-theme=dark]){--bg:#0d1117;--fg:#e6edf3;
--muted:#8b949e;--border:#3d444d;--sidebar:#161b22;--accent:#4493f8;--green:#3fb950;
--yellow:#d29922;--red:#f85149;--code-bg:#161b22;--ok-bar:#3fb950;--stale-bar:#d29922}}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,
sans-serif;margin:0;display:flex;background:var(--bg);color:var(--fg);line-height:1.6}
nav{width:270px;flex-shrink:0;background:var(--sidebar);border-right:1px solid
var(--border);padding:16px;position:sticky;top:0;height:100vh;overflow:auto}
nav h3{margin:0 0 4px;font-size:1.05em}
.brand{display:flex;align-items:center;justify-content:space-between}
#theme-toggle{border:1px solid var(--border);background:var(--bg);color:var(--fg);
border-radius:6px;cursor:pointer;padding:2px 8px;font-size:.9em}
.meta{color:var(--muted);font-size:.78em;margin:4px 0 12px;word-break:break-all}
.coverage{border:1px solid var(--border);border-radius:6px;padding:8px 10px;
margin-bottom:12px;background:var(--bg)}
.cov-row{display:flex;align-items:center;gap:8px;font-size:.78em;margin:3px 0}
.cov-label{width:86px;color:var(--muted);flex-shrink:0}
.cov-bar{flex:1;height:7px;border-radius:4px;background:var(--sidebar);
position:relative;overflow:hidden;display:block}
.cov-bar i{position:absolute;top:0;height:100%}
.cov-ok{background:var(--ok-bar)}
.cov-stale{background:var(--stale-bar)}
.cov-empty{background:repeating-linear-gradient(45deg,transparent,transparent 3px,
var(--border) 3px,var(--border) 6px)}
.cov-count{width:34px;text-align:right;color:var(--muted);flex-shrink:0}
#search{width:100%;padding:6px 10px;border:1px solid var(--border);border-radius:6px;
background:var(--bg);color:var(--fg);margin-bottom:8px;font-size:.85em}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.chip{border:1px solid var(--border);background:var(--bg);color:var(--muted);
border-radius:999px;padding:1px 9px;font-size:.75em;cursor:pointer}
.chip.active{background:var(--accent);border-color:var(--accent);color:#fff}
#catalog a{display:block;padding:2px 0;font-size:.84em;color:var(--accent);
text-decoration:none;word-break:break-all}
#catalog a:hover{text-decoration:underline}
main{flex:1;padding:28px 36px;max-width:960px;margin:0 auto;min-width:0}
main h2{font-size:1.15em;color:var(--muted);border-bottom:1px solid var(--border);
padding-bottom:6px;margin-top:0}
.stale{background:color-mix(in srgb,var(--yellow) 12%,var(--bg));
border-left:4px solid var(--yellow);padding:8px 12px;border-radius:0 6px 6px 0}
.toc{border-left:3px solid var(--border);padding-left:10px;margin:8px 0 16px}
.toc a{display:inline-block;margin-right:10px;font-size:.9em}
h3[id],h4[id]{scroll-margin-top:8px}
pre{background:var(--code-bg);padding:10px;overflow:auto;border-radius:6px;
border:1px solid var(--border);font-size:.85em}
code{background:var(--code-bg);border-radius:4px;padding:1px 5px;font-size:.9em}
pre code{padding:0;background:none;border:none}
table{border-collapse:collapse;margin:10px 0;font-size:.9em;display:block;
overflow:auto;max-width:100%}
th,td{border:1px solid var(--border);padding:5px 12px;text-align:left}
th{background:var(--sidebar)}
blockquote{border-left:3px solid var(--border);margin:8px 0;padding:2px 14px;
color:var(--muted)}
details{margin:4px 0}
details.evidence{border:1px solid var(--border);border-radius:6px;
padding:4px 10px;margin:8px 0;background:var(--bg)}
details.evidence summary{cursor:pointer;color:var(--muted);font-size:.88em;
user-select:none}
details.evidence summary:hover{color:var(--accent)}
.diagram{border:1px solid var(--border);border-radius:6px;margin:8px 0;
padding:8px;overflow:auto;background:var(--bg)}
a{color:var(--accent)}
.ask{border:1px solid var(--border);border-radius:8px;padding:14px 18px;
margin-bottom:22px;background:var(--sidebar)}
.ask h2{border:none;margin:0 0 2px;color:var(--fg)}
.ask-hint{color:var(--muted);font-size:.8em;margin:0 0 8px}
#ask-input{width:100%;max-width:640px;padding:7px 12px;border:1px solid
var(--border);border-radius:6px;background:var(--bg);color:var(--fg);font-size:.92em}
#ask-results{margin-top:10px}
.ask-hit{border:1px solid var(--border);border-radius:6px;background:var(--bg);
padding:8px 12px;margin:6px 0}
.ask-hit a{font-weight:600;text-decoration:none;word-break:break-all}
.ask-hit a:hover{text-decoration:underline}
.ask-hit p{margin:4px 0 0;color:var(--muted);font-size:.85em}
.ask-hit .snippet b{background:color-mix(in srgb,var(--yellow) 30%,var(--bg));
color:var(--fg);font-weight:600;border-radius:3px;padding:0 2px}
.ask-empty{color:var(--muted);font-size:.88em;margin:6px 0}
.ask-claim .claim-statement{margin:6px 0 2px}
.claim-meta{color:var(--muted);font-size:.78em;word-break:break-all}
body.ask-mode main section:not(.ask){display:none}
.site-nav{display:flex;align-items:center;gap:14px;padding:10px 22px;
border-bottom:1px solid var(--border);background:var(--sidebar);
position:sticky;top:0;z-index:5}
.site-nav a{color:var(--accent);text-decoration:none;font-size:.9em}
.site-nav .meta{color:var(--muted);font-size:.78em;flex:1;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.catalog-table{width:100%;border-collapse:collapse;font-size:.88em;
display:table;margin:14px 0}
.catalog-table th{cursor:pointer;user-select:none;white-space:nowrap}
.catalog-table th:hover{color:var(--accent)}
.catalog-table td,.catalog-table th{border:1px solid var(--border);
padding:6px 12px;text-align:left}
.catalog-table a{color:var(--accent);text-decoration:none;word-break:break-all}
.catalog-table a:hover{text-decoration:underline}
.status-pill{display:inline-block;border-radius:999px;padding:0 9px;
font-size:.78em;border:1px solid var(--border)}
.status-verified{color:var(--green);border-color:var(--green)}
.status-stale{color:var(--yellow);border-color:var(--yellow)}
.status-insufficient{color:var(--red);border-color:var(--red);opacity:.85}
.cov-insufficient{background:color-mix(in srgb,var(--red) 45%,var(--sidebar))}
.cov-insufficient-count{color:var(--red);font-size:.9em;margin-left:2px}
.insufficient-row td{opacity:.72}
.muted-cell{color:var(--muted)}
"""


def _render_page_bodies(
    pages: dict[str, bytes], diagram_svgs: dict[str, bytes]
) -> tuple[dict[str, tuple[str, str, str]], list[dict[str, str]]]:
    """Render every Markdown page once for both export surfaces.

    Returns per-page ``(anchor, body_html, toc_html)`` plus the shared
    search index; the standalone file and the site directory reuse the
    same bytes so the two views cannot drift apart.
    """

    bodies: dict[str, tuple[str, str, str]] = {}
    search_index: list[dict[str, str]] = []
    for relative in sorted(pages):
        markdown = pages[relative].decode("utf-8")
        anchor = re.sub(r"[^a-z0-9]+", "-", relative.lower()).strip("-")
        body, page_toc = _markdown_to_html(
            markdown, diagram_svgs, page_anchor=anchor
        )
        bodies[relative] = (anchor, body, page_toc)
        text = re.sub(r"<[^>]+>", " ", body)
        search_index.append(
            {
                "id": anchor,
                "title": relative,
                "type": _page_type(relative),
                "text": re.sub(r"\s+", " ", text).strip()[:4000],
            }
        )
    return bodies, search_index


def _coverage_html(
    objects: dict[str, object],
    insufficient: dict[str, tuple[int, list[str]]] | None = None,
) -> str:
    """Honest per-type coverage bars shared by both export surfaces."""

    rows = _coverage_rows(objects, insufficient)
    coverage_max = max(
        (published + stale + lacking for _t, published, stale, lacking in rows),
        default=1,
    )

    def _render(row: tuple[str, int, int, int]) -> str:
        type_name, published, stale, lacking = row
        title = (
            f"{_h(type_name)}: {published} published, {stale} stale"
            + (f", {lacking} insufficient evidence" if lacking else "")
        )
        count = str(published + stale)
        if lacking:
            count += f'<span class="cov-insufficient-count">+{lacking}</span>'
        if published or stale:
            bar = (
                f'<span class="cov-bar"><i class="cov-ok" style="width:'
                f'{(published / coverage_max) * 100:.1f}%"></i>'
                f'<i class="cov-stale" style="width:'
                f'{(stale / coverage_max) * 100:.1f}%"></i>'
                f'<i class="cov-insufficient" style="width:'
                f'{(lacking / coverage_max) * 100:.1f}%"></i></span>'
            )
        elif lacking:
            bar = (
                f'<span class="cov-bar"><i class="cov-insufficient"'
                f' style="width:100%"></i></span>'
            )
        else:
            bar = '<span class="cov-bar cov-empty"></span>'
            count = "none"
        return (
            f'<div class="cov-row" title="{title}">'
            f'<span class="cov-label">{_h(type_name)}</span>'
            f"{bar}<span class=\"cov-count\">{count}</span></div>"
        )

    return "\n".join(_render(row) for row in rows)


def _chips_html(type_counts: dict[str, int]) -> str:
    return (
        '<button class="chip active" data-type="all"'
        " onclick=\"setType('all')\">all</button>"
        + "".join(
            f'<button class="chip" data-type="{_h(type_name)}"'
            f" onclick=\"setType('{_h(type_name)}')\">{_h(type_name)}"
            f" ({type_counts[type_name]})</button>"
            for type_name in _TYPE_ORDER
            if type_name in type_counts
        )
    )


def _diagram_svgs(objects: dict[str, object]) -> dict[str, bytes]:
    """Pre-render Mermaid sources to inline SVG for both surfaces."""

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
    return diagram_svgs


def _claim_index(
    objects: dict[str, object],
    packs: dict[str, object],
    web_url: str | None,
    rendered: dict[str, tuple[str, str, str]],
) -> list[dict[str, object]]:
    """Claim-granular search entries powering the evidence-only Ask."""

    entries: list[dict[str, object]] = []
    for object_id, canonical in sorted(objects.items()):
        pack = packs.get(object_id)
        evidence_by_id = (
            {item.id: item for item in pack.evidence} if pack else {}
        )
        page_relative = f"{_TYPE_DIRECTORIES[canonical.type]}/{object_id}.md"
        if page_relative not in rendered:
            continue
        anchor = rendered[page_relative][0]
        for claim in canonical.claims:
            evidence: list[dict[str, str]] = []
            for evidence_id in sorted(claim.evidence_ids):
                item = evidence_by_id.get(evidence_id)
                if item is None:
                    continue
                label = f"{item.path}:{item.start_line}-{item.end_line}"
                url = _evidence_permalink(web_url, item)
                evidence.append(
                    {"label": label, "url": url} if url else {"label": label}
                )
            entries.append(
                {
                    "claim": claim.id,
                    "statement": claim.statement,
                    "object": object_id,
                    "type": canonical.type,
                    "anchor": anchor,
                    "evidence": evidence,
                }
            )
    return entries


def _standalone_html(
    root: Path,
    active: str,
    stale_ids: tuple[str, ...],
    orphans: tuple[str, ...],
    rendered: dict[str, tuple[str, str, str]],
    search_index: list[dict[str, str]],
    objects: dict[str, object],
    packs: dict[str, object],
    overlays: dict[str, object],
    web_url: str | None = None,
    insufficient: dict[str, tuple[int, list[str]]] | None = None,
) -> bytes:
    del overlays
    freshness = "current" if not stale_ids else "stale-content"
    sections: list[str] = []
    for relative in sorted(rendered):
        anchor, body, page_toc = rendered[relative]
        sections.append(
            f'<section id="page-{_h(anchor)}" data-page="{_h(relative)}"'
            f' data-type="{_h(_page_type(relative))}">'
            f"<h2>{_h(relative)}</h2>\n"
            + (f'<nav class="toc">{page_toc}</nav>\n' if page_toc else "")
            + f"{body}</section>"
        )
    catalog = "\n".join(
        f'<a href="#page-{rendered[relative][0]}">'
        f"{_h(relative)}</a>"
        for relative in sorted(rendered)
    )
    payload = json.dumps(search_index, ensure_ascii=False, sort_keys=True)
    claims_payload = json.dumps(
        _claim_index(objects, packs, web_url, rendered),
        ensure_ascii=False,
        sort_keys=True,
    )
    commit = _representative_commit(objects)

    coverage_html = _coverage_html(objects, insufficient)
    chip_counts: dict[str, int] = {type_name: 0 for type_name in _TYPE_ORDER}
    for item in search_index:
        if item["type"] in chip_counts:
            chip_counts[item["type"]] += 1
    chips_html = _chips_html(chip_counts)

    script = """
var INDEX=__PAYLOAD__;
var CLAIMS=__CLAIMS_PAYLOAD__;
var TYPE='all';
function esc(s){
 return String(s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
 });
}
function applyFilters(){
 var q=(document.getElementById('search').value||'').toLowerCase();
 document.querySelectorAll('main section').forEach(function(s){
  if(s.classList.contains('ask'))return;
  var id=s.id.replace('page-','');
  var t=s.getAttribute('data-type')||'overview';
  var item=INDEX.filter(function(i){return i.id===id;})[0];
  var textOK=!q||!item||item.text.toLowerCase().indexOf(q)>=0||
   item.title.toLowerCase().indexOf(q)>=0;
  var typeOK=TYPE==='all'||t===TYPE;
  s.style.display=(textOK&&typeOK)?'':'none';
 });
}
function setType(t){
 TYPE=t;
 document.querySelectorAll('.chip').forEach(function(c){
  c.classList.toggle('active',c.getAttribute('data-type')===t);
 });
 applyFilters();
}
document.getElementById('search').addEventListener('input',applyFilters);
document.querySelectorAll('#catalog a').forEach(function(a){
 a.addEventListener('click',function(){
  if(TYPE!=='all'){setType('all');}
  var input=document.getElementById('search');
  if(input.value){input.value='';applyFilters();}
 });
});
function snippet(item,q){
 var text=item.text;var lower=text.toLowerCase();var at=lower.indexOf(q);
 if(at<0){return text.slice(0,160);}
 var start=Math.max(0,at-60);
 var body=text.slice(start,Math.min(text.length,at+q.length+120));
 var head=start>0?'…':'';
 var tail=at+q.length+120<text.length?'…':'';
 return head+body.replace(new RegExp(q.replace(
  /[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'),'gi'),function(m){return '<b>'+m+'</b>';})+tail;
}
function renderAsk(q){
 var box=document.getElementById('ask-results');
 var terms=q.toLowerCase().split(/\\s+/).filter(Boolean);
 if(!terms.length){
  document.body.classList.remove('ask-mode');
  box.innerHTML='';applyFilters();return;
 }
 document.body.classList.add('ask-mode');
 var claimHits=CLAIMS.map(function(c){
  var hay=(c.claim+' '+c.statement+' '+c.object+' '+c.type).toLowerCase();
  var score=terms.reduce(function(n,t){return n+(hay.indexOf(t)>=0?1:0);},0);
  return score===terms.length?c:null;
 }).filter(Boolean);
 if(claimHits.length){
  box.innerHTML=claimHits.map(function(c){
   var ev=c.evidence.map(function(e){
    return e.url?'<a href="'+esc(e.url)+'" target="_blank" rel="noopener">'
     +esc(e.label)+'</a>':esc(e.label);
   }).join(', ');
   return '<div class="ask-hit ask-claim"><a href="#page-'+esc(c.anchor)
    +'" onclick="clearAsk()">'+esc(c.object)+'</a>'
    +'<p class="claim-statement">'+esc(c.statement)+'</p>'
    +'<p class="claim-meta">'+esc(c.claim)
    +(ev?' · evidence: '+ev:'')+'</p></div>';
  }).join('');
  return;
 }
 var hits=INDEX.map(function(item){
  var hay=(item.title+' '+item.text).toLowerCase();
  var score=terms.reduce(function(n,t){return n+(hay.indexOf(t)>=0?1:0);},0);
  return score===terms.length?item:null;
 }).filter(Boolean);
 if(!hits.length){
  box.innerHTML='<p class="ask-empty">知识库未覆盖此问题（evidence-only：'
   +'只检索已验证知识，不做生成式回答）。</p>';
  return;
 }
 box.innerHTML=hits.map(function(item){
  return '<div class="ask-hit"><a href="#page-'+esc(item.id)+
   '" onclick="clearAsk()">'+esc(item.title)+'</a><p class="snippet">'+
   snippet(item,terms[0])+'</p></div>';
 }).join('');
}
function clearAsk(){
 var input=document.getElementById('ask-input');
 if(input){input.value='';}
 document.body.classList.remove('ask-mode');
 document.getElementById('ask-results').innerHTML='';
 applyFilters();
}
document.getElementById('ask-input').addEventListener('input',function(e){
 renderAsk(e.target.value);
});
var btn=document.getElementById('theme-toggle');
var stored=null;
try{stored=localStorage.getItem('wiki-theme');}catch(err){}
if(stored){document.documentElement.setAttribute('data-theme',stored);}
btn.addEventListener('click',function(){
 var cur=document.documentElement.getAttribute('data-theme');
 var prefersDark=window.matchMedia('(prefers-color-scheme: dark)').matches;
 var next=(cur==='dark'||(!cur&&prefersDark))?'light':'dark';
 document.documentElement.setAttribute('data-theme',next);
 try{localStorage.setItem('wiki-theme',next);}catch(err){}
});
""".replace("__PAYLOAD__", payload).replace("__CLAIMS_PAYLOAD__", claims_payload)

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f"<title>{_h(root.name)} knowledge wiki</title>\n"
        f"<style>{_WIKI_STYLE}</style>\n</head>\n<body>\n"
        f"<nav><div class='brand'><h3>{_h(root.name)}</h3>"
        '<button id="theme-toggle" title="Toggle theme">◐</button></div>\n'
        f'<p class="meta">generation: {_h(active)}<br>freshness: {_h(freshness)}<br>'
        f"commit: {_h(commit)}</p>\n"
        '<div class="coverage">\n'
        f"{coverage_html}\n"
        "</div>\n"
        '<input id="search" type="search" placeholder="Search wiki">\n'
        f'<div class="chips">{chips_html}</div>\n'
        f'<div id="catalog">{catalog}</div></nav>\n'
        "<main>\n"
        '<section id="page-ask-view" class="ask">\n'
        "<h2>Ask the knowledge base</h2>\n"
        '<p class="ask-hint">evidence-only — retrieval over verified'
        " knowledge; no generative answers.</p>\n"
        '<input id="ask-input" type="search"'
        ' placeholder="e.g. when is inventory reserved?">\n'
        '<div id="ask-results"></div>\n'
        "</section>\n"
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
        + f"\n</main>\n<script>{script}</script>\n</body>\n</html>\n"
    ).encode("utf-8")


_THEME_TOGGLE_JS = """
var btn=document.getElementById('theme-toggle');
var stored=null;
try{stored=localStorage.getItem('wiki-theme');}catch(err){}
if(stored){document.documentElement.setAttribute('data-theme',stored);}
btn.addEventListener('click',function(){
 var cur=document.documentElement.getAttribute('data-theme');
 var prefersDark=window.matchMedia('(prefers-color-scheme: dark)').matches;
 var next=(cur==='dark'||(!cur&&prefersDark))?'light':'dark';
 document.documentElement.setAttribute('data-theme',next);
 try{localStorage.setItem('wiki-theme',next);}catch(err){}
});
"""

_SITE_ASK_JS = """
function esc(s){
 return String(s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
 });
}
function snippet(item,q){
 var text=item.text;var lower=text.toLowerCase();var at=lower.indexOf(q);
 if(at<0){return text.slice(0,160);}
 var start=Math.max(0,at-60);
 var body=text.slice(start,Math.min(text.length,at+q.length+120));
 var head=start>0?'…':'';
 var tail=at+q.length+120<text.length?'…':'';
 return head+body.replace(new RegExp(q.replace(
  /[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'),'gi'),function(m){return '<b>'+m+'</b>';})+tail;
}
function renderAsk(q){
 var box=document.getElementById('ask-results');
 var terms=q.toLowerCase().split(/\\s+/).filter(Boolean);
 if(!terms.length){box.innerHTML='';return;}
 var claimHits=CLAIMS.map(function(c){
  var hay=(c.claim+' '+c.statement+' '+c.object+' '+c.type).toLowerCase();
  var score=terms.reduce(function(n,t){return n+(hay.indexOf(t)>=0?1:0);},0);
  return score===terms.length?c:null;
 }).filter(Boolean);
 if(claimHits.length){
  box.innerHTML=claimHits.map(function(c){
   var ev=(c.evidence||[]).map(function(e){
    return e.url?'<a href="'+esc(e.url)+'" target="_blank" rel="noopener">'
     +esc(e.label)+'</a>':esc(e.label);
   }).join(', ');
   return '<div class="ask-hit ask-claim"><a href="'+esc(c.href)+'">'
    +esc(c.object)+'</a>'
    +'<p class="claim-statement">'+esc(c.statement)+'</p>'
    +'<p class="claim-meta">'+esc(c.claim)
    +(ev?' · evidence: '+ev:'')+'</p></div>';
  }).join('');
  return;
 }
 var hits=INDEX.map(function(item){
  var hay=(item.title+' '+item.text).toLowerCase();
  var score=terms.reduce(function(n,t){return n+(hay.indexOf(t)>=0?1:0);},0);
  return score===terms.length?item:null;
 }).filter(Boolean);
 if(!hits.length){
  box.innerHTML='<p class="ask-empty">知识库未覆盖此问题（evidence-only：'
   +'只检索已验证知识，不做生成式回答）。</p>';
  return;
 }
 box.innerHTML=hits.map(function(item){
  return '<div class="ask-hit"><a href="'+esc(item.href)+'">'+esc(item.title)+
   '</a><p class="snippet">'+snippet(item,terms[0])+'</p></div>';
 }).join('');
}
document.getElementById('ask-input').addEventListener('input',function(e){
 renderAsk(e.target.value);
});
"""

_SITE_CATALOG_JS = """
var TYPE='all';
function applyFilters(){
 var q=(document.getElementById('catalog-search').value||'').toLowerCase();
 document.querySelectorAll('#catalog-body tr').forEach(function(tr){
  var t=tr.getAttribute('data-type');
  var hay=tr.getAttribute('data-text')||'';
  var typeOK=TYPE==='all'||t===TYPE;
  var textOK=!q||hay.indexOf(q)>=0;
  tr.style.display=(typeOK&&textOK)?'':'none';
 });
}
function setType(t){
 TYPE=t;
 document.querySelectorAll('.chip').forEach(function(c){
  c.classList.toggle('active',c.getAttribute('data-type')===t);
 });
 applyFilters();
}
document.getElementById('catalog-search').addEventListener('input',applyFilters);
var SORT_STATE={col:null,dir:1};
var ORIGINAL=null;
document.querySelectorAll('.catalog-table th').forEach(function(th,i){
 th.addEventListener('click',function(){sortTable(i);});
});
function sortTable(col){
 var tbody=document.getElementById('catalog-body');
 if(!ORIGINAL){
  ORIGINAL=[].slice.call(tbody.rows);
 }
 if(SORT_STATE.col===col){
  SORT_STATE.dir*=-1;
  if(SORT_STATE.dir===-1&&SORT_STATE.wasFlipped){SORT_STATE={col:null,dir:1};}
 }
 if(SORT_STATE.col===null){SORT_STATE={col:col,dir:1,wasFlipped:false};}
 else if(SORT_STATE.dir===1){SORT_STATE.wasFlipped=true;}
 var state=Object.assign({},SORT_STATE);
 if(state.col===null){
  ORIGINAL.forEach(function(tr){tbody.appendChild(tr);});
  return;
 }
 var rows=[].slice.call(tbody.rows);
 rows.sort(function(a,b){
  var av=a.cells[state.col].getAttribute('data-sort')||'';
  var bv=b.cells[state.col].getAttribute('data-sort')||'';
  var an=parseFloat(av);var bn=parseFloat(bv);
  var cmp=(isNaN(an)||isNaN(bv))?av.localeCompare(bv):an-bn;
  return cmp*state.dir;
 });
 rows.forEach(function(tr){tbody.appendChild(tr);});
}
"""


def _site_page_html(
    root_name: str,
    relative: str,
    home: str,
    active: str,
    commit: str,
    freshness: str,
    body: str,
    page_toc: str,
) -> bytes:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f"<title>{_h(root_name)} · {_h(relative)}</title>\n"
        f"<style>{_WIKI_STYLE}</style>\n</head>\n<body>\n"
        f'<nav class="site-nav"><a href="{_h(home)}">← catalog</a>'
        f'<span class="meta">{_h(root_name)} · generation {_h(active)}'
        f" · freshness {_h(freshness)} · commit {_h(commit)}</span>"
        '<button id="theme-toggle" title="Toggle theme">◐</button></nav>\n'
        "<main>\n"
        f"<h2>{_h(relative)}</h2>\n"
        + (f'<nav class="toc">{page_toc}</nav>\n' if page_toc else "")
        + f"{body}\n</main>\n"
        f"<script>{_THEME_TOGGLE_JS}</script>\n</body>\n</html>\n"
    ).encode("utf-8")


def _site_index_html(
    root_name: str,
    active: str,
    stale_ids: tuple[str, ...],
    orphans: tuple[str, ...],
    coverage_html: str,
    chips_html: str,
    catalog_body: str,
    payload: str,
    claims_payload: str,
    commit: str,
) -> bytes:
    freshness = "current" if not stale_ids else "stale-content"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f"<title>{_h(root_name)} knowledge catalog</title>\n"
        f"<style>{_WIKI_STYLE}</style>\n</head>\n<body>\n"
        '<nav class="site-nav"><span class="meta">'
        f"{_h(root_name)} · generation {_h(active)}"
        f" · freshness {_h(freshness)} · commit {_h(commit)}</span>"
        '<button id="theme-toggle" title="Toggle theme">◐</button></nav>\n'
        "<main>\n"
        f"<h1>{_h(root_name)} knowledge catalog</h1>\n"
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
        + '<div class="coverage">\n'
        + coverage_html
        + "\n</div>\n"
        + '<section class="ask">\n<h2>Ask the knowledge base</h2>\n'
        '<p class="ask-hint">evidence-only — retrieval over verified'
        " knowledge; no generative answers.</p>\n"
        '<input id="ask-input" type="search"'
        ' placeholder="e.g. when is inventory reserved?">\n'
        '<div id="ask-results"></div>\n</section>\n'
        '<input id="catalog-search" type="search"'
        ' placeholder="Filter catalog">\n'
        f'<div class="chips">{chips_html}</div>\n'
        '<table class="catalog-table"><thead><tr>'
        "<th>Knowledge ID</th><th>Type</th><th>Status</th>"
        "<th>Claims</th><th>Evidence</th></tr></thead>"
        f'<tbody id="catalog-body">{catalog_body}</tbody></table>\n'
        "</main>\n"
        "<script>var INDEX="
        + payload
        + ";var CLAIMS="
        + claims_payload
        + ";</script>\n"
        f"<script>{_SITE_ASK_JS}</script>\n"
        f"<script>{_SITE_CATALOG_JS}</script>\n"
        f"<script>{_THEME_TOGGLE_JS}</script>\n"
        "</body>\n</html>\n"
    ).encode("utf-8")


def _site_pages(
    root: Path,
    active: str,
    stale_ids: tuple[str, ...],
    orphans: tuple[str, ...],
    rendered: dict[str, tuple[str, str, str]],
    search_index: list[dict[str, str]],
    objects: dict[str, object],
    packs: dict[str, object],
    insufficient: dict[str, tuple[int, list[str]]] | None = None,
) -> dict[str, bytes]:
    """Compile the multi-page static site with relative-path linking."""

    commit = _representative_commit(objects)
    freshness = "current" if not stale_ids else "stale-content"
    pages_out: dict[str, bytes] = {}
    ask_index: list[dict[str, str]] = []
    for relative, (anchor, body, page_toc) in sorted(rendered.items()):
        html_relative = relative[: -len(".md")] + ".html"
        depth = html_relative.count("/")
        home = "../" * depth + "index.html"
        site_body = re.sub(r"\(([^)#]+?)\.md\)", r"(\1.html)", body)
        pages_out[html_relative] = _site_page_html(
            root.name,
            relative,
            home,
            active,
            commit,
            freshness,
            site_body,
            page_toc,
        )
        ask_index.append(
            {
                "title": relative,
                "href": html_relative,
                "type": _page_type(relative),
                "text": next(
                    item["text"] for item in search_index if item["id"] == anchor
                ),
            }
        )

    chip_counts: dict[str, int] = {type_name: 0 for type_name in _TYPE_ORDER}
    for item in search_index:
        if item["type"] in chip_counts:
            chip_counts[item["type"]] += 1

    rows: list[str] = []
    for object_id, canonical in sorted(objects.items()):
        evidence_ids = {
            evidence_id
            for claim in canonical.claims
            for evidence_id in claim.evidence_ids
        }
        status = canonical.validity.status
        status_class = "status-verified" if status == "verified" else ""
        href = (
            f"{_TYPE_DIRECTORIES[canonical.type]}/{_h(object_id)}.html"
        )
        rows.append(
            f'<tr data-type="{_h(canonical.type)}"'
            f' data-text="{_h(object_id.lower() + " " + canonical.type)}">'
            f'<td data-sort="{_h(object_id)}"><a href="{href}">'
            f"{_h(object_id)}</a></td>"
            f'<td data-sort="{_h(canonical.type)}">{_h(canonical.type)}</td>'
            f'<td data-sort="{_h(status)}">'
            f'<span class="status-pill {status_class}">{_h(status)}</span></td>'
            f'<td data-sort="{len(canonical.claims)}" style="text-align:right">'
            f"{len(canonical.claims)}</td>"
            f'<td data-sort="{len(evidence_ids)}" style="text-align:right">'
            f"{len(evidence_ids)}</td></tr>"
        )
    for type_name in _TYPE_ORDER:
        count, lacking_ids = (insufficient or {}).get(type_name, (0, []))
        for target_id in lacking_ids:
            if target_id in objects:
                continue
            rows.append(
                f'<tr class="insufficient-row" data-type="{_h(type_name)}"'
                f' data-text="{_h(target_id.lower() + " " + type_name)}">'
                f'<td data-sort="{_h(target_id)}" class="muted-cell">'
                f"{_h(target_id)}</td>"
                f'<td data-sort="{_h(type_name)}">{_h(type_name)}</td>'
                '<td data-sort="insufficient_evidence">'
                '<span class="status-pill status-insufficient">'
                "insufficient_evidence</span></td>"
                '<td data-sort="0" style="text-align:right">—</td>'
                '<td data-sort="0" style="text-align:right">—</td></tr>'
            )
    claim_entries = _claim_index(objects, packs, None, rendered)
    for entry in claim_entries:
        entry["href"] = (
            f"{_TYPE_DIRECTORIES[entry['type']]}/{entry['object']}.html"
        )
    pages_out["index.html"] = _site_index_html(
        root.name,
        active,
        stale_ids,
        orphans,
        _coverage_html(objects, insufficient),
        _chips_html(chip_counts),
        "".join(rows),
        json.dumps(ask_index, ensure_ascii=False, sort_keys=True),
        json.dumps(claim_entries, ensure_ascii=False, sort_keys=True),
        commit,
    )
    return pages_out


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
    markdown: str,
    diagram_svgs: dict[str, bytes] | None = None,
    *,
    page_anchor: str = "page",
) -> tuple[str, str]:
    """Render Markdown to HTML plus a heading TOC for the page nav.

    Headings carry deterministic anchors; the ``Evidence pointers:``
    list becomes a collapsible <details> block so source references
    stay available without dominating the page.
    """

    lines = markdown.split("\n")
    html_lines: list[str] = []
    toc_entries: list[tuple[int, str, str]] = []
    heading_seq = 0
    paragraph: list[str] = []
    list_items: list[str] = []
    quote_lines: list[str] = []
    code_lines: list[str] | None = None
    code_language = ""
    in_details = 0
    evidence_label_seen = False
    table_lines: list[str] | None = None

    _TABLE_SEPARATOR = re.compile(
        r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$"
    )

    def _table_cells(row: str) -> list[str]:
        cells = re.split(r"(?<!\\)\|", row.strip().strip("|"))
        return [cell.strip().replace(r"\|", "|") for cell in cells]

    def flush_table():
        nonlocal table_lines
        if not table_lines:
            table_lines = None
            return
        rows = table_lines
        table_lines = None
        if len(rows) >= 2 and _TABLE_SEPARATOR.match(rows[1].strip()):
            header = _table_cells(rows[0])
            rendered = [
                "<table><thead><tr>"
                + "".join(f"<th>{_inline_html(cell)}</th>" for cell in header)
                + "</tr></thead><tbody>"
            ]
            for row in rows[2:]:
                rendered.append(
                    "<tr>"
                    + "".join(
                        f"<td>{_inline_html(cell)}</td>"
                        for cell in _table_cells(row)
                    )
                    + "</tr>"
                )
            rendered.append("</tbody></table>")
            html_lines.append("".join(rendered))
        else:
            for row in rows:
                html_lines.append(f"<p>{_inline_html(row)}</p>")

    def flush_paragraph():
        nonlocal evidence_label_seen
        if paragraph:
            html_lines.append(f"<p>{_inline_html(' '.join(paragraph))}</p>")
            evidence_label_seen = (
                " ".join(paragraph).strip() == "Evidence pointers:"
            )
            paragraph.clear()

    def flush_list():
        nonlocal evidence_label_seen
        if list_items:
            claim_evidence_only = all(
                re.sub(r"<[^>]+>", "", item)
                .lstrip()
                .startswith(("Evidence:", "Claims:"))
                for item in list_items
            )
            if evidence_label_seen or claim_evidence_only:
                html_lines.append(
                    '<details class="evidence"><summary>Claims & evidence'
                    "</summary><ul>"
                    + "".join(list_items)
                    + "</ul></details>"
                )
            else:
                html_lines.append("<ul>" + "".join(list_items) + "</ul>")
            list_items.clear()
            evidence_label_seen = False

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
            flush_table()
            code_lines = []
            code_language = ""
            continue
        if stripped.startswith("```") and len(stripped) > 3:
            flush_paragraph()
            flush_list()
            flush_quote()
            flush_table()
            code_lines = []
            code_language = stripped[3:].strip()
            continue
        if not stripped:
            flush_paragraph()
            flush_list()
            flush_quote()
            flush_table()
            continue
        if table_lines is not None or stripped.startswith("|"):
            flush_paragraph()
            flush_list()
            flush_quote()
            if table_lines is None:
                table_lines = []
            table_lines.append(stripped)
            continue
        flush_table()
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            flush_quote()
            level = len(heading.group(1))
            heading_seq += 1
            heading_id = f"h-{page_anchor}-{heading_seq}"
            text = heading.group(2)
            toc_entries.append((level, heading_id, text))
            html_lines.append(
                f'<h{level} id="{_h(heading_id)}">'
                f"{_inline_html(text)}</h{level}>"
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
            continue
        flush_list()
        flush_quote()
        paragraph.append(stripped)
    flush_paragraph()
    flush_list()
    flush_quote()
    flush_table()
    if code_lines is not None:
        raise WikiCompilationError("unterminated fenced code block")
    toc = "".join(
        f'<a href="#{_h(heading_id)}">{_h(text)}</a>'
        for _level, heading_id, text in toc_entries
        if _level >= 2
    )
    return "\n".join(html_lines), toc


__all__ = [
    "WikiCompilationError",
    "WikiCompilationResult",
    "compile_repository_wiki",
]
