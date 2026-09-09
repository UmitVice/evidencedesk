from uuid import uuid4

import pytest

from evidencedesk.db import connection
from evidencedesk.ingest import seed

pytestmark = pytest.mark.integration


def test_session_isolation_and_forgery(client, owner):
    ticket = owner[0]["id"]
    assert client.get(f"/tickets/{ticket}").status_code == 200
    token = client.post("/sessions").json()["token"]
    client.headers["X-Session-Token"] = token
    assert client.get(f"/tickets/{ticket}").status_code == 404
    assert client.get(f"/tickets/{uuid4()}").status_code == 404
    client.headers["X-Session-Token"] = "forged" * 8
    assert client.get("/tickets").status_code == 401


def test_expiry_and_service_auth(client, owner):
    with connection() as conn:
        conn.execute("UPDATE evidence.sessions SET expires_at=now()-interval '1 second'")
    assert client.get("/tickets").status_code == 401
    client.headers["X-Service-Key"] = "forged"
    assert client.post("/sessions").status_code == 401


def test_sources_exclude_foreign_and_obsolete(client, owner):
    with connection() as conn:
        rows = conn.execute(
            "SELECT c.id,c.tenant,d.status FROM evidence.chunks c "
            "JOIN evidence.documents d ON d.id=c.document_id"
        ).fetchall()
    for row in rows:
        expected = 200 if row["tenant"] == "harbor" and row["status"] == "active" else 404
        assert client.get(f"/sources/{row['id']}").status_code == expected


def test_ingestion_is_idempotent(db):
    assert seed() == 0
    with connection() as conn:
        assert conn.execute("SELECT count(*) n FROM evidence.documents").fetchone()["n"] == 24


def test_body_limit(client):
    assert client.post("/sessions", content="x" * 4097).status_code == 413


def test_runtime_database_and_public_privileges(db):
    with connection() as conn:
        assert not conn.execute(
            "SELECT has_schema_privilege('public','evidence','USAGE') ok"
        ).fetchone()["ok"]
        conn.execute("SET LOCAL ROLE evidencedesk_runtime")
        assert conn.execute("SELECT count(*) n FROM evidence.documents").fetchone()["n"] == 24
