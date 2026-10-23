import json
import re
from typing import Any, Literal

import psycopg

from evidencedesk import graph
from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError

Mode = Literal["lexical", "vector", "hybrid"]
COLUMNS = "c.id,c.heading,c.body,d.title,d.source_id,d.version,d.status,d.id document_id"


def search_knowledge(
    tenant: str,
    query: str,
    vector: list[float],
    manifest: dict[str, Any],
    mode: Mode = "hybrid",
    limit: int = 4,
) -> list[dict[str, Any]]:
    config = settings()
    # Expansion always pairs a superseded document with its current version, so only then may
    # obsolete documents be retrieved at all.
    statuses = ["active", "obsolete"] if config.graph_expansion else ["active"]
    lexical_query = " OR ".join(re.findall(r"[a-zA-Z0-9_]+", query)[:60])
    with connection() as conn:
        mismatches = conn.execute(
            "SELECT count(*) n FROM evidence.chunks c JOIN evidence.documents d "
            "ON d.id=c.document_id WHERE c.tenant=%s AND d.status=ANY(%s) "
            "AND (c.embedding_manifest<>%s::jsonb OR c.embedding IS NULL)",
            (tenant, statuses, json.dumps(manifest)),
        ).fetchone()
        if mismatches and mismatches["n"]:
            raise DomainError(
                "corpus_mismatch", "The corpus must be ingested for this AI mode.", 503
            )
        lexical = conn.execute(
            f"SELECT {COLUMNS},"
            "ts_rank_cd(c.search,websearch_to_tsquery('english',%s)) score "
            "FROM evidence.chunks c JOIN evidence.documents d ON d.id=c.document_id "
            "WHERE c.tenant=%s AND d.status=ANY(%s) "
            "AND c.search @@ websearch_to_tsquery('english',%s) "
            "ORDER BY score DESC,c.id LIMIT %s",
            (lexical_query, tenant, statuses, lexical_query, config.candidate_limit),
        ).fetchall()
        vectors = conn.execute(
            f"SELECT {COLUMNS},"
            "c.embedding <=> %s::vector distance "
            "FROM evidence.chunks c JOIN evidence.documents d ON d.id=c.document_id "
            "WHERE c.tenant=%s AND d.status=ANY(%s) AND c.embedding IS NOT NULL "
            "ORDER BY distance,c.id LIMIT %s",
            (str(vector), tenant, statuses, config.candidate_limit),
        ).fetchall()
        vectors = [x for x in vectors if x["distance"] <= config.cosine_distance_limit]
        ranked = rank(mode, lexical, vectors)
        if not config.graph_expansion:
            return ranked[:limit]
        return expand(conn, tenant, vector, ranked, limit)


def rank(
    mode: Mode, lexical: list[dict[str, Any]], vectors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if mode == "lexical":
        return lexical
    if mode == "vector":
        return vectors
    scores: dict[str, float] = {}
    rows: dict[str, dict[str, Any]] = {}
    for ranking in (lexical, vectors):
        for position, row in enumerate(ranking, 1):
            key = str(row["id"])
            rows[key] = row
            scores[key] = scores.get(key, 0) + 1 / (60 + position)
    return [rows[key] for key in sorted(scores, key=lambda key: (-scores[key], key))]


def expand(
    conn: psycopg.Connection[dict[str, Any]],
    tenant: str,
    vector: list[float],
    ranked: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Apply one-hop graph expansion; every query stays inside the caller's tenant."""
    documents = list({row["document_id"] for row in ranked})
    edges = conn.execute(
        "SELECT e.from_document,e.to_document,e.relation,"
        "f.source_id from_source_id,f.title from_title,f.version from_version,"
        "f.status from_status,t.source_id to_source_id,t.title to_title,"
        "t.version to_version,t.status to_status "
        "FROM evidence.document_edges e "
        "JOIN evidence.documents f ON f.id=e.from_document AND f.tenant=e.tenant "
        "JOIN evidence.documents t ON t.id=e.to_document AND t.tenant=e.tenant "
        "WHERE e.tenant=%s AND (e.from_document=ANY(%s) OR e.to_document=ANY(%s))",
        (tenant, documents, documents),
    ).fetchall()
    relations = graph.relations_by_document(edges)
    missing = graph.neighbors(ranked, relations) - {str(row["document_id"]) for row in ranked}
    pulled: list[dict[str, Any]] = []
    if missing:
        # The best chunk of each pulled document for this query, without the cosine cutoff:
        # the relation, not the similarity, is the reason it enters the context.
        pulled = conn.execute(
            f"SELECT DISTINCT ON (d.id) {COLUMNS},c.embedding <=> %s::vector distance "
            "FROM evidence.chunks c JOIN evidence.documents d ON d.id=c.document_id "
            "WHERE c.tenant=%s AND d.id::text=ANY(%s) AND d.status='active' "
            "AND c.embedding IS NOT NULL "
            "ORDER BY d.id,distance,c.id",
            (str(vector), tenant, sorted(missing)),
        ).fetchall()
    return graph.expand(ranked, relations, {str(row["document_id"]): row for row in pulled}, limit)
