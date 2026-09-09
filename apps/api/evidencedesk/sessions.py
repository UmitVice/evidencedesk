import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, Header

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError, missing

PUBLIC_TENANT = "harbor"
SAMPLES = [
    (
        "webhook",
        "Webhook delivery stopped after retries",
        "Our webhook endpoint returned 503. "
        "RelayNest has stopped retrying delivery. How can we recover it?",
    ),
    (
        "credential",
        "API requests fail with an expired credential",
        "Our integration returns 401 with credential_expired. "
        "How should we rotate the API credential safely?",
    ),
    (
        "export",
        "Export download link has expired",
        "The CSV export completed yesterday, "
        "but the download now says link_expired. What should we do?",
    ),
]


def require_service(x_service_key: Annotated[str, Header()] = "") -> None:
    expected = settings().service_key.get_secret_value()
    if len(expected) < 32:
        raise DomainError("service_unavailable", "The sandbox service is not configured.", 503)
    if not secrets.compare_digest(x_service_key, expected):
        raise DomainError("unauthorized", "Service authentication required.", 401)


def session(
    x_session_token: Annotated[str, Header()] = "", _: None = Depends(require_service)
) -> dict[str, Any]:
    if not 40 <= len(x_session_token) <= 128:
        raise DomainError("session_expired", "Start a new sandbox session.", 401)
    digest = hashlib.sha256(x_session_token.encode()).hexdigest()
    with connection() as conn:
        row = conn.execute(
            "SELECT id,tenant,expires_at FROM evidence.sessions "
            "WHERE token_hash=%s AND expires_at > now()",
            (digest,),
        ).fetchone()
    if row is None:
        raise DomainError("session_expired", "Start a new sandbox session.", 401)
    return row


def create_session() -> dict[str, Any]:
    config, token = settings(), secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1001)")
        count = conn.execute("SELECT count(*) AS n FROM evidence.sessions").fetchone()
        if count and count["n"] >= config.session_limit:
            raise DomainError("quota_exhausted", "Sandbox capacity is full. Try again later.", 429)
        row = conn.execute(
            "INSERT INTO evidence.usage_counters VALUES(%s,1,%s) "
            "ON CONFLICT(key) DO UPDATE SET count=usage_counters.count+1 "
            "WHERE usage_counters.count < %s RETURNING count",
            (
                "sessions:" + now.strftime("%Y%m%d%H"),
                now + timedelta(hours=2),
                config.sessions_per_hour,
            ),
        ).fetchone()
        if row is None:
            raise DomainError("quota_exhausted", "Session creation limit reached.", 429)
        result = conn.execute(
            "INSERT INTO evidence.sessions(tenant,token_hash,expires_at) "
            "VALUES(%s,%s,%s) RETURNING id,expires_at",
            (
                PUBLIC_TENANT,
                hashlib.sha256(token.encode()).hexdigest(),
                now + timedelta(hours=config.session_hours),
            ),
        ).fetchone()
        assert result
        for sample, title, body in SAMPLES:
            conn.execute(
                "INSERT INTO evidence.tickets(session_id,tenant,sample,title,body) "
                "VALUES(%s,%s,%s,%s,%s)",
                (result["id"], PUBLIC_TENANT, sample, title, body),
            )
    return {"token": token, "expires_at": result["expires_at"], "mode": config.ai_mode}


def get_ticket(owner: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM evidence.tickets WHERE id=%s AND session_id=%s AND tenant=%s",
            (ticket_id, owner["id"], owner["tenant"]),
        ).fetchone()
    if not row:
        raise missing()
    return row
