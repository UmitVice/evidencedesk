import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from evidencedesk.config import settings
from evidencedesk.errors import DomainError
from evidencedesk.providers import GENERATION_MODEL, LIVE_MANIFEST, CloudflareProvider
from evidencedesk.quotas import reserve


def provider_smoke() -> dict:
    if settings().environment == "production":
        raise DomainError("development_only", "Run provider smoke in development.")
    from evidencedesk.workflow import validate_response

    reserve({"id": "provider-smoke"}, retry=True)
    text = "RelayNest retries failed webhooks after 1 minute, 5 minutes, 30 minutes, and 2 hours."
    adapter = CloudflareProvider()
    vectors = adapter.embed([text])
    source = {"id": str(uuid4()), "body": text}
    raw, usage = adapter.generate({"body": "What is the webhook retry schedule?"}, "", [source])
    answer = validate_response(raw, [source])
    if answer.status != "answered":
        raise DomainError("smoke_failed", "Provider smoke did not answer the supported sample.")
    report = {
        "status": "verified",
        "mode": "live",
        "timestamp": datetime.now(UTC).isoformat(),
        "generation_model": GENERATION_MODEL,
        "embedding_manifest": LIVE_MANIFEST,
        "dimensions": len(vectors[0]),
        "usage": usage,
        "human_review": "pending",
    }
    path = Path(__file__).resolve().parents[3] / "reports" / "provider-smoke.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def require_smoke(path: Path) -> None:
    report = json.loads(path.read_text())
    if (
        report.get("status") != "verified"
        or report.get("mode") != "live"
        or report.get("generation_model") != GENERATION_MODEL
        or report.get("embedding_manifest") != LIVE_MANIFEST
        or report.get("dimensions") != 384
    ):
        raise ValueError("A verified smoke receipt for this exact provider manifest is required")
