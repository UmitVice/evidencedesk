import json
from uuid import uuid4

import pytest

from evidencedesk.db import connection
from evidencedesk.monitoring import render_report
from evidencedesk.quality import needs_review, review_flags

SOURCE = {
    "id": "s1",
    "status": "active",
    "distance": 0.2,
    "body": "Existing credentials cannot have their expiry extended. New credentials expire "
    "after 90 days.",
}


def answer(text: str, quote: str, note: str | None = None) -> dict:
    return {
        "status": "answered",
        "claims": [{"text": text, "citations": [{"source_id": "s1", "quote": quote}]}],
        "proposed_note": note,
    }


def codes(flags: list[dict]) -> list[str]:
    return [flag["code"] for flag in flags]


def test_faithful_answer_has_no_flags():
    good = answer(
        "Existing credentials cannot have their expiry extended.",
        "Existing credentials cannot have their expiry extended.",
        "Expiry cannot be extended; create a replacement.",
    )
    assert review_flags(good, [SOURCE], "Can we extend the credential?") == []


def test_number_the_quote_does_not_contain_is_flagged():
    wrong = answer("New credentials expire after 30 days.", "New credentials expire after 90 days.")
    assert "number_mismatch" in codes(review_flags(wrong, [SOURCE], "When do they expire?"))
    # A number from the question may be repeated without being an invention.
    restated = answer("New credentials expire after 90 days, not 365.", "expire after 90 days.")
    assert "number_mismatch" not in codes(review_flags(restated, [SOURCE], "Is it 365 days?"))


def test_inverted_negation_is_flagged_but_an_omitted_clause_is_not():
    inverted = answer(
        "Existing credentials can have their expiry extended.",
        "Existing credentials cannot have their expiry extended.",
    )
    assert "negation_dropped" in codes(review_flags(inverted, [SOURCE]))
    omitted = answer(
        "Verification uses the webhook signing secret.",
        "Signature verification uses the webhook signing secret, not an API credential.",
    )
    assert "negation_dropped" not in codes(review_flags(omitted, [SOURCE]))


def test_unsupported_claim_and_note_number_are_flagged():
    flags = codes(
        review_flags(
            answer(
                "Do not execute apply_approved_note immediately.",
                "New credentials expire after 90 days.",
                "Rotate within 14 days.",
            ),
            [SOURCE],
        )
    )
    assert "weak_quote_support" in flags
    assert "note_adds_number" in flags


def test_outdated_conflicting_and_weak_sources_are_flagged():
    outdated = {**SOURCE, "status": "obsolete", "relations": [{"relation": "conflicts_with"}]}
    good = answer("New credentials expire after 90 days.", "New credentials expire after 90 days.")
    flags = codes(review_flags(good, [outdated]))
    assert {"outdated_source", "conflicting_sources"} <= set(flags)
    assert "weak_retrieval" in codes(review_flags(good, [{**SOURCE, "distance": 0.4}]))
    assert "weak_retrieval" in codes(review_flags(good, [{**SOURCE, "distance": None}]))


def test_fallback_is_information_only():
    good = answer("New credentials expire after 90 days.", "New credentials expire after 90 days.")
    flags = review_flags(good, [SOURCE], fell_back=True)
    assert codes(flags) == ["fallback_model"]
    assert not needs_review(flags)


def test_abstention_is_never_flagged_for_retrieval():
    abstain = {"status": "insufficient_evidence", "claims": [], "proposed_note": None}
    assert review_flags(abstain, []) == []


def test_report_escapes_ticket_and_answer_content():
    run = {
        "id": uuid4(),
        "created_at": "2026-10-30",
        "question": "<script>alert(1)</script>",
        "title": "T",
        "ticket": "",
        "model": "gpt-6-luna",
        "flags": [{"code": "number_mismatch", "severity": "review", "message": "m"}],
        "result": answer("<b>x</b>", "q"),
    }
    page = render_report(
        {"days": 7, "complete": 1, "failed": 0, "flagged": 1, "flags": []}, [run]
    )
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "<b>x</b>" not in page


@pytest.mark.integration
def test_analysis_stores_review_flags(client, owner):
    ticket = next(t for t in owner if t["sample"] == "webhook")
    run = client.post(f"/tickets/{ticket['id']}/analyze", json={}).json()
    assert isinstance(run["trace"]["review_flags"], list)


@pytest.mark.integration
def test_quality_summary_counts_live_runs_without_content(client, owner):
    ticket = owner[0]
    flagged = {"review_flags": [{"code": "number_mismatch", "severity": "review", "message": "m"}],
               "attempts": 1, "generation_model": "gpt-6-luna"}
    info = {"review_flags": [{"code": "fallback_model", "severity": "info", "message": "m"}],
            "attempts": 1, "generation_model": "@cf/meta/llama-3.1-8b-instruct-fast"}
    with connection(migration=True) as conn:
        session = conn.execute(
            "SELECT session_id,tenant FROM evidence.tickets WHERE id=%s", (ticket["id"],)
        ).fetchone()
        for status, trace in [("complete", flagged), ("complete", info), ("failed", {})]:
            conn.execute(
                "INSERT INTO evidence.runs(session_id,tenant,ticket_id,ticket_version,mode,"
                "status,question,trace) VALUES(%s,%s,%s,1,'live',%s,'secret question',%s)",
                (session["session_id"], session["tenant"], ticket["id"], status,
                 json.dumps(trace)),
            )
    response = client.get("/quality/summary", headers={"X-Session-Token": ""})
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["complete"], data["failed"], data["flagged"]) == (2, 1, 1)
    assert data["flags"] == [
        {"code": "fallback_model", "count": 1},
        {"code": "number_mismatch", "count": 1},
    ]
    assert {m["model"] for m in data["models"]} == {
        "gpt-6-luna",
        "@cf/meta/llama-3.1-8b-instruct-fast",
    }
    assert "secret question" not in response.text
    assert client.get("/quality/summary", headers={"X-Service-Key": "wrong"}).status_code == 401
