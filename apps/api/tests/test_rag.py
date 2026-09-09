import json
from uuid import uuid4

import httpx
import pytest

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError
from evidencedesk.ingest import FIXTURE_MANIFEST, fixture_vector
from evidencedesk.providers import CloudflareProvider
from evidencedesk.retrieval import search_knowledge
from evidencedesk.tokenization import check_embedding_input, token_count
from evidencedesk.workflow import validate_response


def test_citation_validation_and_no_capability_escalation():
    source = str(uuid4())
    rows = [{"id": source, "body": "A valid supporting quote about retries."}]
    valid = {
        "status": "answered",
        "claims": [
            {
                "text": "Retry guidance",
                "citations": [{"source_id": source, "quote": rows[0]["body"]}],
            }
        ],
        "proposed_note": "Review retries.",
    }
    assert validate_response(json.dumps(valid), rows).status == "answered"
    for raw in [
        "invalid JSON",
        json.dumps({**valid, "tool": "execute_sql"}),
        json.dumps(valid).replace(source, str(uuid4())),
        json.dumps(valid).replace("A valid supporting quote", "A forged supporting quote"),
        json.dumps({"status": "insufficient_evidence", "claims": [], "proposed_note": "Apply"}),
    ]:
        with pytest.raises(DomainError):
            validate_response(raw, rows)


def test_real_token_budget():
    assert token_count("A short English document.") < 512
    with pytest.raises(ValueError):
        check_embedding_input("credential " * 600)


@pytest.mark.integration
def test_retrieval_filters_before_context(db):
    for mode in ("lexical", "vector", "hybrid"):
        results = search_knowledge(
            "harbor", "webhook", fixture_vector("webhook"), FIXTURE_MANIFEST, mode
        )
        assert all(x["source_id"] not in ("summit-private", "summit-export") for x in results)
        assert all(x["version"] == 2 for x in results)
    with pytest.raises(DomainError, match="corpus_mismatch"):
        search_knowledge("harbor", "webhook", fixture_vector("webhook"), {"model": "different"})


@pytest.mark.integration
def test_analysis_persists_and_survives_new_client(client, owner):
    ticket = next(t for t in owner if t["sample"] == "webhook")
    response = client.post(f"/tickets/{ticket['id']}/analyze", json={})
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["mode"] == "simulated"
    assert run["status"] == "complete"
    assert run["result"]["status"] == "answered"
    assert client.get(f"/runs/{run['id']}").json()["result"] == run["result"]
    with connection() as conn:
        assert conn.execute("SELECT count(*) n FROM evidence.runs").fetchone()["n"] == 1
    assert (
        client.post(f"/tickets/{ticket['id']}/analyze", json={"question": "arbitrary"}).status_code
        == 422
    )


@pytest.mark.parametrize(
    "status,code",
    [(429, "provider_quota"), (503, "provider_transient"), (401, "provider_unavailable")],
)
def test_provider_errors_are_sanitized(monkeypatch, status, code):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    settings.cache_clear()
    adapter = CloudflareProvider(
        httpx.MockTransport(lambda request: httpx.Response(status, text="secret"))
    )
    with pytest.raises(DomainError) as error:
        adapter.embed(["hello"])
    assert error.value.code == code
    assert "secret" not in error.value.message
    settings.cache_clear()
