"""Provision a restricted local runtime login and update only the ignored API environment."""
import os
import secrets
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from psycopg import sql

from evidencedesk.config import settings
from evidencedesk.db import connection

config = settings()
url = urlsplit(config.database_url.get_secret_value())
if config.environment not in ("development", "test") or url.hostname not in ("localhost", "127.0.0.1"):
    raise SystemExit("This helper only provisions the local EvidenceDesk database")
role = "evidencedesk_local_runtime"
if url.username == role:
    raise SystemExit("Restricted local runtime is already configured")
password = secrets.token_urlsafe(32)
with connection(migration=True) as conn:
    if conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
        raise SystemExit("The role already exists; preserving its credentials")
    conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} IN ROLE evidencedesk_runtime")
                 .format(sql.Identifier(role), sql.Literal(password)))
path = Path(__file__).resolve().parents[1] / ".env"
netloc = f"{role}:{quote(password, safe='')}@{url.hostname}:{url.port or 5432}"
runtime = urlunsplit(url._replace(netloc=netloc))
lines = path.read_text().splitlines()
path.write_text("\n".join("DATABASE_URL=" + runtime if line.startswith("DATABASE_URL=")
                          else line for line in lines) + "\n")
os.chmod(path, 0o600)
print("Restricted local runtime login configured; credentials were not printed.")
