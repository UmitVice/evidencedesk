from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from evidencedesk.config import settings
from evidencedesk.errors import DomainError


@contextmanager
def connection(*, migration: bool = False) -> Iterator[psycopg.Connection[dict[str, Any]]]:
    config = settings()
    url = (config.migration_database_url if migration else config.database_url).get_secret_value()
    if not url:
        raise DomainError("database_unavailable", "The sandbox database is not configured.", 503)
    try:
        with psycopg.connect(
            url,
            row_factory=dict_row,
            prepare_threshold=None,
            connect_timeout=5,
            options="-c statement_timeout=5000 -c lock_timeout=3000",
        ) as conn:
            yield conn
    except psycopg.OperationalError as exc:
        raise DomainError(
            "database_unavailable", "The sandbox database is unavailable.", 503
        ) from exc
