import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError
from evidencedesk.evaluation import DATASET, retrieval_metrics
from evidencedesk.quotas import reserve


def test_dataset_split_integrity():
    cases = json.loads(DATASET.read_text())
    assert len(cases) == 40
    assert Counter(c["split"] for c in cases) == {"development": 24, "holdout": 16}
    groups = {}
    for case in cases:
        groups.setdefault(case["group"], set()).add(case["split"])
    assert all(len(splits) == 1 for splits in groups.values())


def test_document_metrics_denominator_and_duplicate_citations():
    metrics = retrieval_metrics([["a", "a", "b"], ["x"], ["a"]], [["b"], ["a"], []])
    assert metrics == {"n": 2, "recall_at_5": 0.5, "mrr": 0.25}


def test_live_report_does_not_count_local_abstention_as_generation(monkeypatch):
    import evidencedesk.evaluation as evaluation
    from evidencedesk.config import Settings
    from evidencedesk.providers import FixtureProvider

    config = Settings(database_url="postgresql://localhost/evidencedesk_eval")
    monkeypatch.setattr(evaluation, "settings", lambda: config)
    monkeypatch.setattr(evaluation, "CloudflareProvider", FixtureProvider)
    monkeypatch.setattr(evaluation, "reserve", lambda *args, **kwargs: None)
    monkeypatch.setattr(evaluation, "search_knowledge", lambda *args: [])
    report = evaluation.run_evaluation("live", "development", 1)
    assert report["generation_attempts"] == report["generation_completions"] == 0
    assert report["outcomes"][0]["answer"]["status"] == "insufficient_evidence"
    assert report["latency"]["n"] == 1
    assert report["latency"]["p95_ms"] is None


def test_evaluation_validation_details_exclude_raw_model_content(monkeypatch):
    import evidencedesk.evaluation as evaluation
    from evidencedesk.config import Settings
    from evidencedesk.providers import FixtureProvider

    class Invalid(FixtureProvider):
        def generate(self, ticket, question, evidence):
            return json.dumps({
                "status": "answered", "claims": [], "proposed_note": "private input marker",
            }), None

    config = Settings(database_url="postgresql://localhost/evidencedesk_eval")
    monkeypatch.setattr(evaluation, "settings", lambda: config)
    monkeypatch.setattr(evaluation, "CloudflareProvider", Invalid)
    monkeypatch.setattr(evaluation, "reserve", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        evaluation, "search_knowledge", lambda *args: [{"source_id": "webhook-retries"}]
    )
    report = evaluation.run_evaluation("live", "development", 1)
    outcome = report["outcomes"][0]
    assert outcome["validation_issues"] == [{"field": [], "type": "value_error"}]
    assert outcome["error_code"] == "invalid_model_output"
    assert outcome["generation_completed"] is True
    assert "private input marker" not in json.dumps(report)
    assert "answer" not in outcome


@pytest.mark.integration
def test_atomic_analysis_quota(db):
    def attempt(_):
        try:
            reserve({"id": "concurrent-session"})
            return True
        except DomainError as exc:
            assert exc.code == "quota_exhausted"
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(8))) == settings().analyses_per_minute
    with connection() as conn:
        rows = conn.execute("SELECT count FROM evidence.usage_counters").fetchall()
        assert all(row["count"] == 2 for row in rows)


@pytest.mark.integration
def test_quota_blocks_before_embedding(client, owner, monkeypatch):
    from evidencedesk.providers import FixtureProvider

    called = []
    original = FixtureProvider.embed

    def embed(self, texts):
        called.append(1)
        return original(self, texts)

    monkeypatch.setattr(FixtureProvider, "embed", embed)
    ticket = owner[0]["id"]
    for _ in range(2):
        assert client.post(f"/tickets/{ticket}/analyze", json={}).status_code == 200
    assert client.post(f"/tickets/{ticket}/analyze", json={}).status_code == 429
    assert len(called) == 2


@pytest.mark.integration
def test_live_ingestion_only_reembeds_changed_chunks(db, monkeypatch, tmp_path):
    import shutil

    import evidencedesk.ingest as ingest
    from evidencedesk.live_ingest import ingest_live
    from evidencedesk.providers import CloudflareProvider

    calls = []
    for path in ingest.DATA.glob("*.md"):
        shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(ingest, "DATA", tmp_path)

    def embed(self, texts):
        calls.append(len(texts))
        return [ingest.fixture_vector(text) for text in texts]

    monkeypatch.setattr(CloudflareProvider, "embed", embed)
    try:
        assert ingest_live() == 24
        assert ingest_live() == 0
        path = tmp_path / "01-webhook-retries.md"
        path.write_text(path.read_text() + "\n\nA changed documented recovery detail.\n")
        assert ingest_live() == 1
        assert calls == [16, 8, 1]
    finally:
        from psycopg.types.json import Jsonb

        with connection(migration=True) as conn:
            conn.execute(
                "UPDATE evidence.chunks SET embedding_manifest=%s",
                (Jsonb(ingest.FIXTURE_MANIFEST),),
            )
