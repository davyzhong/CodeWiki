from __future__ import annotations


def relations_of(canonical: object) -> list[tuple[str, str, str]]:
    """One-hop relations as ``(source, target, predicate)`` triples.

    Shared by the MCP ``knowledge_get_related`` tool and the site
    detail pages so the two surfaces cannot disagree about relations.
    """

    rows: list[tuple[str, str, str]] = []
    for field, default in (
        ("dependencies", "depends on"),
        ("relations", "relates to"),
    ):
        for item in getattr(canonical, field, ()) or ():
            target = getattr(item, "target", None)
            if isinstance(target, str):
                predicate = getattr(item, "predicate", None) or default
                rows.append((canonical.id, target, predicate))
    for target in getattr(canonical, "related_objects", ()) or ():
        if isinstance(target, str):
            rows.append((canonical.id, target, "related to"))
    for relationship in getattr(canonical, "relationships", ()) or ():
        target = getattr(relationship, "target", None)
        predicate = getattr(relationship, "predicate", "relates to")
        if isinstance(target, str):
            rows.append((canonical.id, target, predicate))
    return sorted(set(rows))


__all__ = ["relations_of"]
