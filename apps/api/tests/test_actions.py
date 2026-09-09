import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from evidencedesk.db import connection
from main import app

pytestmark = pytest.mark.integration


def proposal(client, owner):
    ticket = next(t for t in owner if t["sample"] == "webhook")
    result = client.post(f"/tickets/{ticket['id']}/analyze", json={})
    assert result.status_code == 200, result.text
    return result.json()["proposal"], ticket["id"]


def test_concurrent_repeated_approval_one_effect(client, owner):
    action, ticket = proposal(client, owner)
    headers = dict(client.headers)

    def approve(_):
        with TestClient(app) as concurrent:
            return concurrent.post(
                f"/proposals/{action['id']}/decision", headers=headers, json={"decision": "approve"}
            )

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(approve, range(8)))
    assert all(r.status_code == 200 for r in responses)
    assert len({r.json()["note_id"] for r in responses}) == 1
    history = client.get(f"/tickets/{ticket}").json()
    assert [n["content"] for n in history["notes"]] == [action["content"]]
    assert history["version"] == 2
    assert [a["event"] for a in history["audit"]] == ["proposed", "applied"]


def test_rejection_no_mutation_and_cannot_approve(client, owner):
    action, ticket = proposal(client, owner)
    url = f"/proposals/{action['id']}/decision"
    assert client.post(url, json={"decision": "reject"}).status_code == 200
    assert client.post(url, json={"decision": "approve"}).status_code == 409
    result = client.get(f"/tickets/{ticket}").json()
    assert result["notes"] == [] and result["version"] == 1


def test_stale_and_foreign_and_edited(client, owner):
    action, ticket = proposal(client, owner)
    url = f"/proposals/{action['id']}/decision"
    assert (
        client.post(url, json={"decision": "approve", "content": "replacement"}).status_code == 422
    )
    with connection() as conn:
        conn.execute("UPDATE evidence.tickets SET version=version+1 WHERE id=%s", (ticket,))
    assert (
        client.post(url, json={"decision": "approve"}).json()["error"]["code"] == "proposal_stale"
    )
    client.headers["X-Session-Token"] = client.post("/sessions").json()["token"]
    assert client.post(url, json={"decision": "approve"}).status_code == 404


def test_immutable_database_guard(client, owner):
    action, _ = proposal(client, owner)
    with pytest.raises(psycopg.errors.RaiseException), connection(migration=True) as conn:
        conn.execute("UPDATE evidence.proposals SET content='edited' WHERE id=%s", (action["id"],))


def test_pending_survives_application_restart(client, owner):
    action, ticket = proposal(client, owner)
    script = """
import json, sys
from fastapi.testclient import TestClient
from main import app
payload = json.load(sys.stdin)
with TestClient(app) as client:
    detail = client.get('/tickets/' + payload['ticket'], headers=payload['headers']).json()
    run = client.get('/runs/' + detail['runs'][0]['id'], headers=payload['headers']).json()
    print(json.dumps({'id': run['proposal']['id'], 'status': run['proposal']['status']}))
"""
    fresh = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps({"ticket": ticket, "headers": dict(client.headers)}),
        text=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
    assert json.loads(fresh.stdout) == {"id": action["id"], "status": "pending"}


def test_expired_proposal(client, owner):
    action, _ = proposal(client, owner)
    # Create an already-expired proposal without modifying immutable persisted content.
    with connection(migration=True) as conn:
        conn.execute("DELETE FROM evidence.proposals WHERE id=%s", (action["id"],))
        run = conn.execute("SELECT * FROM evidence.runs LIMIT 1").fetchone()
        row = conn.execute(
            "INSERT INTO evidence.proposals(run_id,session_id,tenant,ticket_id,"
            "expected_version,content,content_hash,expires_at) "
            "VALUES(%s,%s,%s,%s,1,%s,%s,now()-interval '1 second') RETURNING id",
            (
                run["id"],
                run["session_id"],
                run["tenant"],
                run["ticket_id"],
                action["content"],
                action["content_hash"],
            ),
        ).fetchone()
    result = client.post(f"/proposals/{row['id']}/decision", json={"decision": "approve"})
    assert result.json()["error"]["code"] == "proposal_expired"


def test_approve_reject_race_has_one_final_state(client, owner):
    action, ticket = proposal(client, owner)

    def decide(decision):
        with TestClient(app) as other:
            return other.post(
                f"/proposals/{action['id']}/decision",
                headers=dict(client.headers),
                json={"decision": decision},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(decide, ["approve", "reject"]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    history = client.get(f"/tickets/{ticket}").json()
    final = history["audit"][-1]["event"]
    assert len(history["notes"]) == (1 if final == "applied" else 0)
    assert len(history["audit"]) == 2


def test_competing_proposals_make_second_stale(client, owner):
    first, ticket = proposal(client, owner)
    second, _ = proposal(client, owner)
    assert (
        client.post(f"/proposals/{first['id']}/decision", json={"decision": "approve"}).status_code
        == 200
    )
    result = client.post(f"/proposals/{second['id']}/decision", json={"decision": "approve"})
    assert result.json()["error"]["code"] == "proposal_stale"
    assert len(client.get(f"/tickets/{ticket}").json()["notes"]) == 1


def test_runtime_role_cannot_edit_proposals_or_corpus(client, owner):
    action, _ = proposal(client, owner)
    for statement in [
        "UPDATE evidence.documents SET title='tampered'",
        "UPDATE evidence.proposals SET content='tampered'",
    ]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection() as conn:
            conn.execute("SET LOCAL ROLE evidencedesk_runtime")
            from psycopg import sql

            conn.execute(sql.SQL(statement))
    with connection() as conn:
        conn.execute("SET LOCAL ROLE evidencedesk_runtime")
        assert conn.execute(
            "SELECT id FROM evidence.proposals WHERE id=%s", (action["id"],)
        ).fetchone()
