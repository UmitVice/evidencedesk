import json
import re
from typing import Any, Literal

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError

Mode = Literal["lexical", "vector", "hybrid"]


def search_knowledge(
    tenant: str,
    query: str,
    vector: list[float],
    manifest: dict[str, Any],
    mode: Mode = "hybrid",
    limit: int = 4,
) -> list[dict[str, Any]]:
    config = settings()
    lexical_query = " OR ".join(re.findall(r"[a-zA-Z0-9_]+", query)[:60])
    with connection() as conn:
        mismatches = conn.execute(
            "SELECT count(*) n FROM evidence.chunks c JOIN evidence.documents d "
            "ON d.id=c.document_id WHERE c.tenant=%s AND d.status='active' "
            "AND (c.embedding_manifest<>%s::jsonb OR c.embedding IS NULL)",
            (tenant, json.dumps(manifest)),
        ).fetchone()
        if mismatches and mismatches["n"]:
            raise DomainError(
                "corpus_mismatch", "The corpus must be ingested for this AI mode.", 503
            )
        lexical = conn.execute(
            "SELECT c.id,c.heading,c.body,d.title,d.source_id,d.version,d.status,"
            "ts_rank_cd(c.search,websearch_to_tsquery('english',%s)) score "
            "FROM evidence.chunks c JOIN evidence.documents d ON d.id=c.document_id "
            "WHERE c.tenant=%s AND d.status='active' "
            "AND c.search @@ websearch_to_tsquery('english',%s) "
            "ORDER BY score DESC,c.id LIMIT %s",
            (lexical_query, tenant, lexical_query, config.candidate_limit),
        ).fetchall()
        vectors = conn.execute(
            "SELECT c.id,c.heading,c.body,d.title,d.source_id,d.version,d.status,"
            "c.embedding <=> %s::vector distance "
            "FROM evidence.chunks c JOIN evidence.documents d ON d.id=c.document_id "
            "WHERE c.tenant=%s AND d.status='active' AND c.embedding IS NOT NULL "
            "ORDER BY distance,c.id LIMIT %s",
            (str(vector), tenant, config.candidate_limit),
        ).fetchall()
    vectors = [x for x in vectors if x["distance"] <= config.cosine_distance_limit]
    if mode == "lexical":
        return lexical[:limit]
    if mode == "vector":
        return vectors[:limit]
    scores: dict[str, float] = {}
    rows: dict[str, dict[str, Any]] = {}
    for ranking in (lexical, vectors):
        for rank, row in enumerate(ranking, 1):
            key = str(row["id"])
            rows[key] = row
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    return [rows[key] for key in sorted(scores, key=lambda key: (-scores[key], key))[:limit]]
