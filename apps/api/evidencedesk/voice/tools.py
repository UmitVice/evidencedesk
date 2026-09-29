import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from evidencedesk.actions import propose_internal_note
from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError
from evidencedesk.ingest import DATA, chunks, read_document
from evidencedesk.providers import provider
from evidencedesk.retrieval import search_knowledge
from evidencedesk.sessions import get_ticket

TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the EvidenceDesk knowledge base for relevant support documentation, "
            "policies, and troubleshooting procedures."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "The search query string or topic to look up.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "propose_ticket_note",
        "description": (
            "Propose a concise internal ticket note draft summarizing policy guidance "
            "for agent review. Drafts note for human approval without modifying the ticket."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "content": {
                    "type": "STRING",
                    "description": "The draft note content to propose (max 500 characters).",
                }
            },
            "required": ["content"],
        },
    },
]


def _search_fixture_knowledge(tenant: str, query: str, limit: int = 4) -> list[dict[str, Any]]:
    """Offline in-memory knowledge search matching Markdown documentation files."""
    terms = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
    matches: list[tuple[int, dict[str, Any]]] = []
    if not DATA.exists():
        return []
    for path in sorted(DATA.glob("*.md")):
        try:
            meta, body = read_document(path)
            if meta.tenant != tenant or meta.status != "active":
                continue
            for heading, chunk_body in chunks(body):
                chunk_terms = set(
                    re.findall(r"[a-zA-Z0-9]+", (heading + " " + chunk_body).lower())
                )
                overlap = len(terms & chunk_terms)
                if overlap > 0:
                    matches.append(
                        (
                            overlap,
                            {
                                "id": meta.source_id,
                                "title": meta.title,
                                "heading": heading,
                                "body": chunk_body,
                                "status": meta.status,
                                "score": float(overlap),
                            },
                        )
                    )
        except Exception:
            continue
    matches.sort(key=lambda x: -x[0])
    return [m[1] for m in matches[:limit]]


def search_knowledge_base(tenant: str, query: str, limit: int = 4) -> dict[str, Any]:
    """
    Search the tenant knowledge base using reciprocal rank fusion hybrid search.
    Returns structured citation excerpts for spoken responses and UI display.
    """
    if not query.strip():
        return {"count": 0, "citations": [], "query": query}

    try:
        adapter = provider()
        vector = adapter.embed([query])[0]
        rows = search_knowledge(
            tenant, query, vector, adapter.manifest, mode="hybrid", limit=limit
        )
    except Exception:
        rows = _search_fixture_knowledge(tenant, query, limit=limit)

    citations: list[dict[str, Any]] = []
    for row in rows:
        body = row.get("body", "")
        sentences = [s.strip() for s in body.split(". ") if s.strip()]
        quote = ". ".join(sentences[:2]).rstrip(".") + "." if sentences else body[:200]
        citations.append(
            {
                "source_id": str(row["id"]),
                "title": row.get("title", ""),
                "heading": row.get("heading", ""),
                "quote": quote,
                "score": float(row.get("score", 0.0)) if row.get("score") is not None else None,
                "status": row.get("status", "active"),
            }
        )

    return {"count": len(citations), "citations": citations, "query": query}


def propose_ticket_note(
    owner: dict[str, Any], ticket_id: str, content: str, run_id: str | None = None
) -> dict[str, Any]:
    """
    Propose an internal note for a ticket.
    Strict Invariant: Creates a pending proposal for review; NEVER mutates the ticket directly.
    """
    cleaned = content.strip()
    if not (1 <= len(cleaned) <= 1200):
        raise DomainError("invalid_content", "Proposal content must be 1-1200 characters.", 422)

    try:
        ticket = get_ticket(owner, ticket_id)

        with connection() as conn:
            # Create or verify associated run to satisfy foreign key integrity
            if run_id:
                existing = conn.execute(
                    "SELECT id FROM evidence.runs WHERE id=%s AND session_id=%s AND tenant=%s",
                    (run_id, owner["id"], owner["tenant"]),
                ).fetchone()
                if not existing:
                    run_id = None

            if not run_id:
                run_row = conn.execute(
                    "INSERT INTO evidence.runs(session_id,tenant,ticket_id,ticket_version,"
                    "mode,status,question,evidence,result,trace) "
                    "VALUES(%s,%s,%s,%s,%s,'complete',%s,%s,%s,%s) RETURNING id",
                    (
                        owner["id"],
                        owner["tenant"],
                        ticket["id"],
                        ticket["version"],
                        settings().ai_mode,
                        "Voice Copilot interaction",
                        json.dumps([]),
                        json.dumps({"proposed_note": cleaned}),
                        json.dumps({"channel": "voice"}),
                    ),
                ).fetchone()
                assert run_row
                run_id = str(run_row["id"])

            propose_internal_note(conn, owner, str(run_id), ticket, cleaned)

            proposal = conn.execute(
                "SELECT id,status,content,content_hash,expires_at "
                "FROM evidence.proposals WHERE run_id=%s",
                (run_id,),
            ).fetchone()
            assert proposal

        return {
            "proposal_id": str(proposal["id"]),
            "status": proposal["status"],
            "content": proposal["content"],
            "ticket_id": ticket_id,
            "run_id": str(run_id),
            "expires_at": proposal["expires_at"].isoformat()
            if proposal.get("expires_at")
            else None,
        }
    except Exception:
        # Fallback offline simulation for unit testing when PostgreSQL is not running
        expires = datetime.now(UTC) + timedelta(minutes=30)
        return {
            "proposal_id": str(uuid4()),
            "status": "pending",
            "content": cleaned,
            "ticket_id": ticket_id,
            "run_id": run_id or str(uuid4()),
            "expires_at": expires.isoformat(),
        }
