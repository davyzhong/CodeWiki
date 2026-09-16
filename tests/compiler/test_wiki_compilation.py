from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from knowledge_compiler.storage import GenerationPublisher


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/integration"))
sys.path.insert(0, str(ROOT / "tests/storage"))

from test_generation_publication import _verified_inputs  # noqa: E402
from test_typed_publication import canonicalize  # noqa: E402


def _persist_verified(root: Path, canonical: object, pack: object) -> None:
    import json

    target = root / ".knowledge/state/runs/manual-wiki/targets" / canonical.id
    target.mkdir(parents=True, exist_ok=True)
    (target / "verified.json").write_text(
        json.dumps(
            {
                "canonical": canonical.model_dump(mode="json"),
                "evidence_pack": pack.model_dump(mode="json"),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def publish_world(root: Path, generation: str = "gen-wiki-001") -> dict[str, str]:
    module, pack = _verified_inputs()
    _persist_verified(root, module, pack)
    items: list[tuple[object, object | None]] = [(module, pack)]
    ids = {"module": module.id}
    for type_name in ("architecture", "flow", "rule", "tech-stack"):
        canonical = canonicalize(type_name).canonical
        assert canonical is not None
        ids[type_name] = canonical.id
        items.append((canonical, None))
    GenerationPublisher(root).publish_generation(generation, tuple(items))
    return ids


def test_compile_writes_catalog_aggregates_sources_and_standalone_html(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    ids = publish_world(tmp_path)

    result = compile_repository_wiki(tmp_path)

    wiki = tmp_path / ".knowledge/views/wiki"
    for name in (
        "index.md",
        "architecture.md",
        "rules.md",
        "tech-stack.md",
        "sources.md",
    ):
        assert (wiki / name).is_file(), name
    index = (wiki / "index.md").read_text(encoding="utf-8")
    for object_id in ids.values():
        assert object_id in index
    assert "sources.md" in index
    html_path = tmp_path / ".knowledge/exports/repo-wiki.html"
    assert html_path == result.html_path
    html = html_path.read_bytes()
    assert b"<!doctype html>" in html
    assert b"search" in html
    assert b"<svg" in html
    for object_id in ids.values():
        assert object_id.encode("utf-8") in html
    sources = (wiki / "sources.md").read_text(encoding="utf-8")
    assert "src/shop" in sources
    assert ids["module"] in sources
    manifest = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest["wiki_generation"] == manifest["active_generation"]
    assert result.generation == manifest["active_generation"]
    assert result.stale_object_ids == ()
    assert result.orphaned_overlay_ids == ()


def test_compile_is_deterministic_across_runs(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    compile_repository_wiki(tmp_path)
    first = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in sorted((tmp_path / ".knowledge").rglob("*"))
        if path.is_file()
        and "state" not in path.relative_to(tmp_path).parts
    }
    compile_repository_wiki(tmp_path)
    second = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in sorted((tmp_path / ".knowledge").rglob("*"))
        if path.is_file()
        and "state" not in path.relative_to(tmp_path).parts
    }
    assert first == second


def test_stale_object_page_carries_expiry_banner(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    module, pack = _verified_inputs()
    _persist_verified(tmp_path, module, pack)
    GenerationPublisher(tmp_path).publish_generation(
        "gen-stale-001", ((module, pack),)
    )
    data = module.model_dump(mode="json")
    data["validity"] = {
        "status": "stale",
        "verified_commit": module.validity.verified_commit,
        "stale_reason": "evidence changed",
    }
    from knowledge_compiler.contracts.knowledge import ModuleKnowledge

    stale = ModuleKnowledge.model_validate(data)
    GenerationPublisher(tmp_path).publish_generation(
        "gen-stale-002", ((stale, pack),)
    )

    result = compile_repository_wiki(tmp_path)

    assert result.stale_object_ids == (module.id,)
    page = (
        tmp_path / ".knowledge/views/wiki/modules" / f"{module.id}.md"
    ).read_text(encoding="utf-8")
    assert "Stale knowledge" in page
    assert "evidence changed" in page
    assert page.index("Stale knowledge") < page.index("## ")
    html = (
        tmp_path / ".knowledge/exports/repo-wiki.html"
    ).read_text(encoding="utf-8")
    assert "stale-content" in html


def test_orphaned_archive_renders_warning(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    archive = tmp_path / ".knowledge/human/archive/modules/module.shop.retired.yaml"
    archive.parent.mkdir(parents=True)
    archive.write_text("archived: true\n", encoding="utf-8")

    result = compile_repository_wiki(tmp_path)

    assert result.orphaned_overlay_ids == ("module.shop.retired",)
    index = (
        tmp_path / ".knowledge/views/wiki/index.md"
    ).read_text(encoding="utf-8")
    assert "Orphaned human knowledge" in index
    assert "module.shop.retired" in index


def test_human_overlay_merges_into_aggregate_and_object_pages(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    ids = publish_world(tmp_path)
    overlay = (
        tmp_path
        / ".knowledge/human/architecture"
        / f"{ids['architecture']}.yaml"
    )
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {ids['architecture']}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections:\n"
        "  - field: summary\n"
        "    mode: override\n"
        "    text: Human operational summary.\n"
        "    basis: incident review\n"
        "notes: []\n",
        encoding="utf-8",
    )

    compile_repository_wiki(tmp_path)

    aggregate = (
        tmp_path / ".knowledge/views/wiki/architecture.md"
    ).read_text(encoding="utf-8")
    assert "Human operational summary." in aggregate
    assert "Machine-verified original" in aggregate
    object_page = (
        tmp_path
        / ".knowledge/views/wiki/architecture"
        / f"{ids['architecture']}.md"
    ).read_text(encoding="utf-8")
    assert "Human operational summary." in object_page


def test_compile_failure_leaves_wiki_generation_behind(tmp_path: Path) -> None:
    from knowledge_compiler.compiler import wiki as wiki_module
    from knowledge_compiler.compiler.wiki import (
        WikiCompilationError,
        compile_repository_wiki,
    )

    publish_world(tmp_path, "gen-wiki-001")
    compile_repository_wiki(tmp_path)
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish_generation(
        "gen-wiki-002", ((module, pack),)
    )
    manifest_before = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest_before["active_generation"] == "gen-wiki-002"

    def fail(*_args: object) -> None:
        raise OSError("injected write failure")

    original = wiki_module.compile_repository_wiki.__globals__[
        "_stamp_wiki_generation"
    ]
    wiki_module._stamp_wiki_generation = fail  # type: ignore[assignment]
    try:
        with pytest.raises(WikiCompilationError):
            compile_repository_wiki(tmp_path)
    finally:
        wiki_module._stamp_wiki_generation = original  # type: ignore[assignment]

    manifest_after = yaml.safe_load(
        (tmp_path / ".knowledge/manifest.yaml").read_bytes()
    )
    assert manifest_after["wiki_generation"] == "gen-wiki-001"
    assert manifest_after["active_generation"] == "gen-wiki-002"


def test_stale_wiki_stamp_preserves_newer_generation_manifest(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import _stamp_wiki_generation

    publish_world(tmp_path, "gen-wiki-old")
    manifest_path = tmp_path / ".knowledge/manifest.yaml"
    stale_manifest = yaml.safe_load(manifest_path.read_bytes())
    module, pack = _verified_inputs()
    GenerationPublisher(tmp_path).publish_generation(
        "gen-wiki-new", ((module, pack),)
    )

    _stamp_wiki_generation(manifest_path, stale_manifest, "gen-wiki-old")

    current = yaml.safe_load(manifest_path.read_bytes())
    assert current["active_generation"] == "gen-wiki-new"
    assert current["agent_views_generation"] == "gen-wiki-new"
    assert current["wiki_generation"] == "gen-wiki-old"


def test_unterminated_code_fence_fails_closed() -> None:
    from knowledge_compiler.compiler.wiki import (
        WikiCompilationError,
        _markdown_to_html,
    )

    with pytest.raises(WikiCompilationError):
        _markdown_to_html("```mermaid\ngraph TD\n")


def test_html_export_has_heading_anchors_toc_and_collapsible_evidence(
    tmp_path: Path,
) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    result = compile_repository_wiki(tmp_path)
    html = result.html_path.read_text(encoding="utf-8")

    assert '<h3 id="h-' in html
    assert '<nav class="toc">' in html
    assert '<details class="evidence">' in html
    assert "<summary>Claims & evidence</summary>" in html


def test_html_export_is_deterministic(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    compile_repository_wiki(tmp_path)
    html_path = tmp_path / ".knowledge/exports/repo-wiki.html"
    first = html_path.read_bytes()
    compile_repository_wiki(tmp_path)
    assert html_path.read_bytes() == first


def test_compile_writes_multi_page_site_directory(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    ids = publish_world(tmp_path)
    result = compile_repository_wiki(tmp_path)
    site = tmp_path / ".knowledge/exports/site"

    index = (site / "index.html").read_text(encoding="utf-8")
    assert "knowledge catalog" in index
    module_page = (
        site / "modules" / f"{ids['module']}.html"
    ).read_text(encoding="utf-8")
    assert "<!doctype html>" in module_page
    assert 'href="../index.html"' in module_page
    # Markdown links are rewritten to sibling HTML pages.
    assert ".md)" not in module_page.split("</style>", 1)[1]
    sources_page = (site / "sources.html").read_text(encoding="utf-8")
    assert "Source index" in sources_page
    # Both surfaces exist after one compile.
    assert result.html_path.is_file()


def test_site_and_html_are_deterministic_across_runs(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    compile_repository_wiki(tmp_path)

    def snapshot() -> dict[str, bytes]:
        site = tmp_path / ".knowledge/exports/site"
        return {
            str(path.relative_to(site)): path.read_bytes()
            for path in sorted(site.rglob("*.html"))
        }

    first = snapshot()
    compile_repository_wiki(tmp_path)
    assert snapshot() == first


def test_web_url_config_adds_evidence_permalinks(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki
    from knowledge_compiler.config import KnowledgeConfig, write_config

    module, pack = _verified_inputs()
    commit = pack.evidence[0].commit
    path = pack.evidence[0].path
    write_config(
        tmp_path / ".knowledge/config.yaml",
        KnowledgeConfig.model_validate(
            {
                "schema_version": "0.1",
                "repository_provider": "local-git",
                "evidence_provider": "codewiki",
                "language": "zh",
                "worker_profiles": {
                    "extraction_profile": "extraction-v1",
                    "validation_profile": None,
                },
                "exclusions": [],
                "scope_limits": {"max_files": 10000, "max_bytes": 52428800},
                "default_context_budget": 6000,
                "web_url": "https://github.com/fixture/probe-shop",
            }
        ),
    )
    publish_world(tmp_path)
    compile_repository_wiki(tmp_path)

    expected = (
        f"(https://github.com/fixture/probe-shop/blob/{commit}/{path}"
    )
    modules_dir = tmp_path / ".knowledge/views/wiki/modules"
    module_md = next(modules_dir.glob("*.md"))
    assert expected in module_md.read_text(encoding="utf-8")
    sources_md = (
        tmp_path / ".knowledge/views/wiki/sources.md"
    ).read_text(encoding="utf-8")
    assert expected in sources_md


def test_missing_web_url_degrades_to_plain_citations(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    compile_repository_wiki(tmp_path)
    sources_md = (
        tmp_path / ".knowledge/views/wiki/sources.md"
    ).read_text(encoding="utf-8")
    assert "blob/" not in sources_md


def test_typed_wiki_renders_evidence_citations_when_pack_given() -> None:
    from types import SimpleNamespace

    from knowledge_compiler.compiler.typed_views import compile_typed_wiki

    outcome = canonicalize("flow")
    assert outcome.canonical is not None
    canonical = outcome.canonical
    claim = canonical.claims[0]
    item = SimpleNamespace(
        id=sorted(claim.evidence_ids)[0],
        path="src/shop/checkout.py",
        start_line=4,
        end_line=11,
        commit="c" * 40,
    )
    pack = SimpleNamespace(evidence=[item])
    page = compile_typed_wiki(
        canonical,
        None,
        pack=pack,
        web_url="https://github.com/fixture/probe-shop",
    ).decode("utf-8")
    assert "- Evidence:" in page
    assert "https://github.com/fixture/probe-shop/blob/" in page


def test_typed_wiki_without_pack_has_no_evidence_lines() -> None:
    from knowledge_compiler.compiler.typed_views import compile_typed_wiki

    outcome = canonicalize("rule")
    assert outcome.canonical is not None
    page = compile_typed_wiki(outcome.canonical).decode("utf-8")
    assert "- Evidence:" not in page


def test_both_surfaces_embed_claim_level_ask_index(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    compile_repository_wiki(tmp_path)
    single = (
        tmp_path / ".knowledge/exports/repo-wiki.html"
    ).read_text(encoding="utf-8")
    assert "var CLAIMS=" in single
    assert '"statement"' in single
    assert '"evidence"' in single
    site = (
        tmp_path / ".knowledge/exports/site/index.html"
    ).read_text(encoding="utf-8")
    assert "var CLAIMS=" in site
    assert '"href"' in site


def test_insufficient_targets_surface_in_catalog_and_coverage(
    tmp_path: Path,
) -> None:
    import json as _json

    from knowledge_compiler.compiler.wiki import (
        _insufficient_targets,
        compile_repository_wiki,
    )

    publish_world(tmp_path)
    runs_dir = tmp_path / ".knowledge/state/runs/run-insufficient-001"
    runs_dir.mkdir(parents=True)
    insufficient_target = {
        "target_id": "tech-stack.probe-shop.runtime",
        "object_type": "tech-stack",
        "topic": "runtime stack",
        "evidence_seeds": (),
        "state": "done",
        "attempt": 1,
        "repair_attempts": 0,
        "required": True,
        "priority": 1,
        "result": "insufficient_evidence",
        "published_object_id": None,
        "request_digest": "sha256:" + "1" * 64,
        "result_digest": None,
        "diagnostics": ("no bounded evidence available",),
        "lease": None,
    }
    (runs_dir / "run.json").write_text(
        _json.dumps(
            {
                "run_id": "run-insufficient-001",
                "repository_id": "fixture/probe-shop",
                "snapshot_id": "sha256:" + "2" * 64,
                "executor": "llm",
                "active": False,
                "targets": (insufficient_target,),
            }
        ),
        encoding="utf-8",
    )

    counts = _insufficient_targets(tmp_path)
    assert counts == {
        "tech-stack": (1, ["tech-stack.probe-shop.runtime"])
    }

    compile_repository_wiki(tmp_path)
    site = (
        tmp_path / ".knowledge/exports/site/index.html"
    ).read_text(encoding="utf-8")
    assert "insufficient-row" in site
    assert "tech-stack.probe-shop.runtime" in site
    single = (
        tmp_path / ".knowledge/exports/repo-wiki.html"
    ).read_text(encoding="utf-8")
    assert "cov-insufficient-count" in single


def test_insufficient_targets_tolerate_missing_runs(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import _insufficient_targets

    assert _insufficient_targets(tmp_path) == {}


def test_catalog_status_chips_and_overlay_badges(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    ids = publish_world(tmp_path)
    overlay = (
        tmp_path / ".knowledge/human/architecture" / f"{ids['architecture']}.yaml"
    )
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        "schema_version: '0.1'\n"
        f"object_id: {ids['architecture']}\n"
        "updated_at: '2026-08-25T12:00:00+08:00'\n"
        "sections:\n"
        "  - field: summary\n"
        "    mode: override\n"
        "    text: Human operational summary.\n"
        "    basis: incident review\n"
        "notes: []\n",
        encoding="utf-8",
    )
    compile_repository_wiki(tmp_path)

    index = (
        tmp_path / ".knowledge/exports/site/index.html"
    ).read_text(encoding="utf-8")
    assert 'data-status="verified"' in index
    assert "setStatus('insufficient_evidence')" in index
    assert "overlay-badge" in index

    detail = (
        tmp_path
        / ".knowledge/exports/site/architecture"
        / f"{ids['architecture']}.html"
    ).read_text(encoding="utf-8")
    assert "human knowledge: 1 overlay entries" in detail

    single = (
        tmp_path / ".knowledge/exports/repo-wiki.html"
    ).read_text(encoding="utf-8")
    assert "@media (max-width:900px)" in single


def test_site_history_page_lists_runs_and_diff_payload(tmp_path: Path) -> None:
    import json as _json

    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    runs_dir = tmp_path / ".knowledge/state/runs/run-hist-001"
    runs_dir.mkdir(parents=True)
    (runs_dir / "run.json").write_text(
        _json.dumps(
            {
                "run_id": "run-hist-001",
                "repository_id": "fixture/probe-shop",
                "snapshot_id": "sha256:" + "2" * 64,
                "executor": "llm",
                "active": False,
                "targets": [],
            }
        ),
        encoding="utf-8",
    )
    compile_repository_wiki(tmp_path)

    history = (
        tmp_path / ".knowledge/exports/site/history.html"
    ).read_text(encoding="utf-8")
    assert "Generation timeline" in history
    assert "run-hist-001" in history
    assert "diffRuns" in history
    index = (
        tmp_path / ".knowledge/exports/site/index.html"
    ).read_text(encoding="utf-8")
    assert 'href="history.html"' in index


def test_detail_page_renders_related_card(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    ids = publish_world(tmp_path)
    compile_repository_wiki(tmp_path)
    flow_page = (
        tmp_path
        / ".knowledge/exports/site/flows"
        / f"{ids['flow']}.html"
    ).read_text(encoding="utf-8")
    # The fixture flow references the module via relations or claims;
    # the card renders whenever forward or inbound relations exist.
    if "Related knowledge" in flow_page:
        assert "<svg" in flow_page

    module_page = (
        tmp_path
        / ".knowledge/exports/site/modules"
        / f"{ids['module']}.html"
    ).read_text(encoding="utf-8")
    assert "Related knowledge" in module_page
    assert "<svg" in module_page


def test_exported_surfaces_carry_aria_semantics(tmp_path: Path) -> None:
    from knowledge_compiler.compiler.wiki import compile_repository_wiki

    publish_world(tmp_path)
    compile_repository_wiki(tmp_path)
    single = (
        tmp_path / ".knowledge/exports/repo-wiki.html"
    ).read_text(encoding="utf-8")
    assert 'id="ask-results" aria-live="polite"' in single
    assert 'aria-label="Search wiki"' in single
    assert 'aria-label="Toggle color theme"' in single
    assert "aria-pressed" in single

    site = (
        tmp_path / ".knowledge/exports/site/index.html"
    ).read_text(encoding="utf-8")
    assert 'aria-pressed="true"' in site
    assert 'aria-label="Filter catalog"' in site
    assert 'aria-label="Ask the knowledge base"' in site
    assert "<th scope=\"col\"><button>" in site
    assert "announceSort" in site
    assert "aria-sort" in site
