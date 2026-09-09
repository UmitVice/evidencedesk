from datetime import UTC, datetime
from typing import Any, Literal

import psycopg

from evidencedesk.db import connection
from evidencedesk.errors import DomainError, missing
from evidencedesk.ingest import digest


def propose_internal_note(
    conn: psycopg.Connection[dict[str, Any]],
    owner: dict[str, Any],
    run_id: str,
    ticket: dict[str, Any],
    content: str,
) -> None:
    row = conn.execute(
        "INSERT INTO evidence.proposals(run_id,session_id,tenant,ticket_id,expected_version,"
        "content,content_hash,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,now()+interval '30 minutes') "
        "RETURNING id",
        (
            run_id,
            owner["id"],
            owner["tenant"],
            ticket["id"],
            ticket["version"],
            content,
            digest(content),
        ),
    ).fetchone()
    assert row
    conn.execute(
        "INSERT INTO evidence.audit_events(session_id,tenant,ticket_id,proposal_id,event) "
        "VALUES(%s,%s,%s,%s,'proposed')",
        (owner["id"], owner["tenant"], ticket["id"], row["id"]),
    )


def apply_approved_note(
    owner: dict[str, Any], proposal_id: str, decision: Literal["approve", "reject"]
) -> dict[str, Any]:
    with connection() as conn:
        proposal = conn.execute(
            "SELECT * FROM evidence.proposals WHERE id=%s AND session_id=%s "
            "AND tenant=%s FOR UPDATE",
            (proposal_id, owner["id"], owner["tenant"]),
        ).fetchone()
        if not proposal:
            raise missing()
        if digest(proposal["content"]) != proposal["content_hash"]:
            raise DomainError(
                "proposal_edited", "Proposal integrity failed. Regenerate the analysis.", 409
            )
        if proposal["status"] == "applied" and decision == "approve":
            note = conn.execute(
                "SELECT id FROM evidence.notes WHERE proposal_id=%s", (proposal_id,)
            ).fetchone()
            assert note
            return {"status": "applied", "note_id": str(note["id"]), "replayed": True}
        if proposal["status"] != "pending":
            raise DomainError(
                "proposal_decided", "This proposal already has a final decision.", 409
            )
        if proposal["expires_at"] <= datetime.now(UTC):
            raise DomainError(
                "proposal_expired", "This proposal expired. Regenerate the analysis.", 409
            )
        ticket = conn.execute(
            "SELECT version FROM evidence.tickets WHERE id=%s AND session_id=%s "
            "AND tenant=%s FOR UPDATE",
            (proposal["ticket_id"], owner["id"], owner["tenant"]),
        ).fetchone()
        if not ticket or ticket["version"] != proposal["expected_version"]:
            raise DomainError("proposal_stale", "The ticket changed. Regenerate the analysis.", 409)
        status, note_id = "rejected", None
        if decision == "approve":
            note = conn.execute(
                "INSERT INTO evidence.notes(proposal_id,session_id,tenant,ticket_id,"
                "content) VALUES(%s,%s,%s,%s,%s) RETURNING id",
                (
                    proposal_id,
                    owner["id"],
                    owner["tenant"],
                    proposal["ticket_id"],
                    proposal["content"],
                ),
            ).fetchone()
            assert note
            note_id, status = str(note["id"]), "applied"
            conn.execute(
                "UPDATE evidence.tickets SET version=version+1 WHERE id=%s",
                (proposal["ticket_id"],),
            )
        conn.execute(
            "UPDATE evidence.proposals SET status=%s,decided_at=now() WHERE id=%s",
            (status, proposal_id),
        )
        conn.execute(
            "INSERT INTO evidence.audit_events(session_id,tenant,ticket_id,proposal_id,event) "
            "VALUES(%s,%s,%s,%s,%s)",
            (owner["id"], owner["tenant"], proposal["ticket_id"], proposal_id, status),
        )
    return {"status": status, "note_id": note_id, "replayed": False}


def ticket_history(owner: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    with connection() as conn:
        notes = conn.execute(
            "SELECT id,content,created_at FROM evidence.notes WHERE session_id=%s "
            "AND tenant=%s AND ticket_id=%s ORDER BY created_at",
            (owner["id"], owner["tenant"], ticket_id),
        ).fetchall()
        audit = conn.execute(
            "SELECT event,proposal_id,created_at FROM evidence.audit_events "
            "WHERE session_id=%s AND tenant=%s AND ticket_id=%s ORDER BY created_at",
            (owner["id"], owner["tenant"], ticket_id),
        ).fetchall()
        runs = conn.execute(
            "SELECT id,status,mode,created_at FROM evidence.runs WHERE session_id=%s "
            "AND tenant=%s AND ticket_id=%s ORDER BY created_at DESC LIMIT 10",
            (owner["id"], owner["tenant"], ticket_id),
        ).fetchall()
    return {"notes": notes, "audit": audit, "runs": runs}
