from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.environ.get("KNOWLEDGE_RUN_LIVE") != "1",
    reason="set KNOWLEDGE_RUN_LIVE=1 for live CodeWiki/LiteLLM coverage",
)
def test_live_primary_build_uses_public_codewiki_and_configured_model() -> None:
    from knowledge_compiler.building import run_configured_build
    from knowledge_compiler.config import load_config

    configured_root = os.environ.get("KNOWLEDGE_LIVE_REPOSITORY")
    if not configured_root:
        pytest.fail("KNOWLEDGE_LIVE_REPOSITORY must name an explicit test repository")
    root = Path(configured_root).resolve()
    outcome = run_configured_build(
        repository_root=root,
        executor="llm",
        config=load_config(root / ".knowledge/config.yaml"),
    )
    assert outcome.status in {"complete", "partial"}
    assert outcome.published_object_ids
