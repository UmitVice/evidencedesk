from datetime import UTC, datetime, timedelta
from typing import Any

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError


def reserve(owner: dict[str, Any], *, retry: bool = False) -> None:
    config, now = settings(), datetime.now(UTC)
    keys = [
        ("environment:" + now.strftime("%Y%m%d"), config.attempts_per_environment_day),
        (f"session:{owner['id']}:" + now.strftime("%Y%m%d"), config.attempts_per_session_day),
    ]
    if not retry:
        keys.append(
            (f"minute:{owner['id']}:" + now.strftime("%Y%m%d%H%M"), config.analyses_per_minute)
        )
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1003)")
        for key, limit in keys:
            row = conn.execute(
                "INSERT INTO evidence.usage_counters VALUES(%s,1,%s) "
                "ON CONFLICT(key) DO UPDATE SET count=usage_counters.count+1 "
                "WHERE usage_counters.count < %s RETURNING count",
                (key, now + timedelta(days=2), limit),
            ).fetchone()
            if row is None:
                raise DomainError(
                    "quota_exhausted", "Analysis budget exhausted. Try again later.", 429
                )
