from uuid import uuid4

import psycopg
import pytest

from evidencedesk import graph
from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.ingest import (
    DATA,
    FIXTURE_MANIFEST,
    Metadata,
    derive_edges,
    document_id,
    fixture_vector,
    read_document,
)
from evidencedesk.retrieval import search_knowledge


def meta(source_id: str, version: int, status: str = "active", **extra) -> Metadata:
    return Metadata.model_validate(
        {
            "tenant": extra.pop("tenant", "harbor"),
            "source_id": source_id,
            "title": source_id.title(),
            "version": version,
            "status": status,
            "product": "RelayNest",
            **extra,
        }
    )


def test_versions_supersede_every_older_version_in_one_hop():
    chain = [meta("limits", 1, "obsolete"), meta("limits", 2, "obsolete"), meta("limits", 3)]
    edges = {(e.from_document, e.to_document, e.relation) for e in derive_edges(chain)}
    v1, v2, v3 = (document_id(x) for x in chain)
    assert edges == {(v3, v2, "supersedes"), (v3, v1, "supersedes"), (v2, v1, "supersedes")}


def test_front_matter_relations_resolve_to_the_active_version_in_the_same_tenant():
    old, current = meta("cap", 1, "obsolete"), meta("cap", 2)
    notes = meta("notes", 2, related=[{"source_id": "cap", "relation": "conflicts_with"}])
    edges = derive_edges([old, current, notes])
    conflicts = {(e.from_document, e.to_document) for e in edges if e.relation == "conflicts_with"}
    assert conflicts == {
        (document_id(notes), document_id(current)),
        (document_id(current), document_id(notes)),
    }
    assert all(e.tenant == "harbor" for e in edges)
    foreign = meta("cap", 2, tenant="summit")
    with pytest.raises(ValueError, match="unknown source"):
        derive_edges([foreign, notes])


def test_inconsistent_version_metadata_is_rejected():
    with pytest.raises(ValueError, match="newer than the active"):
        derive_edges([meta("x", 1), meta("x", 2, "obsolete")])
    with pytest.raises(ValueError, match="itself"):
        derive_edges([meta("x", 2, related=[{"source_id": "x", "relation": "see_also"}])])
    with pytest.raises(ValueError):
        meta("x", 2, related=[{"source_id": "x", "relation": "executes"}])


def test_corpus_graph_is_valid():
    documents = [read_document(path)[0] for path in sorted(DATA.glob("*.md"))]
    relations = {(e.relation, e.origin) for e in derive_edges(documents)}
    assert relations == {
        ("supersedes", "version"),
        ("conflicts_with", "front_matter"),
        ("depends_on", "front_matter"),
        ("see_also", "front_matter"),
    }


def row(source_id: str, status: str = "active", document: str | None = None) -> dict:
    return {
        "id": str(uuid4()),
        "document_id": document or source_id,
        "source_id": source_id,
        "status": status,
        "version": 1 if status == "obsolete" else 2,
        "body": source_id,
    }


def edge(start: dict, end: dict, relation: str) -> dict:
    result = {"from_document": start["document_id"], "to_document": end["document_id"]}
    for prefix, item in (("from", start), ("to", end)):
        for key in ("source_id", "version", "status"):
            result[f"{prefix}_{key}"] = item[key]
        result[f"{prefix}_title"] = item["source_id"]
    return {**result, "relation": relation}


def test_expansion_pulls_current_version_before_superseded_row_and_keeps_limit():
    legacy = row("limits", "obsolete", "limits-v1")
    current = row("limits", document="limits-v2")
    others = [row(f"other-{i}") for i in range(4)]
    relations = graph.relations_by_document([edge(current, legacy, "supersedes")])
    result = graph.expand([legacy, *others], relations, {"limits-v2": current}, 4)
    expected = [current, legacy, *others[:2]]
    assert [x["id"] for x in result] == [x["id"] for x in expected]
    assert result[0]["expansion"] == {"via": "superseded_by", "anchor": "limits"}
    assert result[1]["relations"][0]["relation"] == "superseded_by"
    assert result[1]["relations"][0]["evidence_id"] == current["id"]
    assert result[0]["relations"][0]["relation"] == "supersedes"


def test_superseded_row_without_current_version_is_dropped():
    legacy, other = row("limits", "obsolete"), row("other")
    assert [x["id"] for x in graph.expand([legacy, other], {}, {}, 4)] == [other["id"]]


def test_conflicts_and_dependencies_are_pulled_but_see_also_is_only_annotated():
    cap, notes, retention, status = row("cap"), row("notes"), row("retention"), row("status")
    tail = row("tail")
    edges = [
        edge(cap, notes, "conflicts_with"),
        edge(notes, cap, "conflicts_with"),
        edge(cap, retention, "depends_on"),
        edge(cap, status, "see_also"),
    ]
    relations = graph.relations_by_document(edges)
    result = graph.expand([cap, tail, notes], relations, {"retention": retention}, 4)
    assert [x["source_id"] for x in result] == ["cap", "notes", "retention", "tail"]
    assert [x["relation"] for x in result[0]["relations"]] == [
        "conflicts_with",
        "depends_on",
        "see_also",
    ]
    assert result[0]["relations"][2]["evidence_id"] is None
    assert result[2]["relations"] == [
        {**relations["retention"][0], "evidence_id": cap["id"]},
    ]
    assert result[2]["relations"][0]["relation"] == "required_by"


@pytest.mark.integration
def test_graph_is_seeded_tenant_scoped_and_readable_by_runtime(db):
    with connection() as conn:
        conn.execute("SET LOCAL ROLE evidencedesk_runtime")
        rows = conn.execute(
            "SELECT e.relation,f.tenant ft,t.tenant tt,f.source_id fs,t.source_id ts "
            "FROM evidence.document_edges e "
            "JOIN evidence.documents f ON f.id=e.from_document "
            "JOIN evidence.documents t ON t.id=e.to_document"
        ).fetchall()
    assert rows and all(x["ft"] == x["tt"] == "harbor" for x in rows)
    assert any(
        x["relation"] == "supersedes" and x["fs"] == x["ts"] == "credential-expiry" for x in rows
    )
    with connection(migration=True) as conn:
        documents = conn.execute(
            "SELECT id,tenant FROM evidence.documents WHERE source_id IN "
            "('webhook-retries','summit-export') ORDER BY tenant"
        ).fetchall()
        with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.transaction():
            conn.execute(
                "INSERT INTO evidence.document_edges VALUES(%s,%s,%s,'see_also','front_matter')",
                ("harbor", documents[0]["id"], documents[-1]["id"]),
            )


@pytest.mark.integration
def test_graph_expansion_is_off_by_default_and_pairs_versions_when_on(db, monkeypatch):
    query = "Can an owner extend an API credential expiry by 30 days?"
    vector = fixture_vector(query)
    baseline = search_knowledge("harbor", query, vector, FIXTURE_MANIFEST, "hybrid")
    assert all(x["status"] == "active" and "relations" not in x for x in baseline)
    monkeypatch.setenv("GRAPH_EXPANSION", "true")
    settings.cache_clear()
    for mode in ("lexical", "vector", "hybrid"):
        expanded = search_knowledge("harbor", query, vector, FIXTURE_MANIFEST, mode)
        assert len(expanded) <= 4
        assert all(x["source_id"] not in ("summit-private", "summit-export") for x in expanded)
        for index, item in enumerate(expanded):
            if item["status"] == "obsolete":
                current = [x["evidence_id"] for x in item["relations"] if x["status"] == "active"]
                assert current and current[0] in [str(x["id"]) for x in expanded[:index]]
    expanded = search_knowledge("harbor", query, vector, FIXTURE_MANIFEST, "hybrid")
    assert any(x["status"] == "obsolete" for x in expanded)
    settings.cache_clear()
