import argparse
import hashlib
from pathlib import Path
from typing import LiteralString, cast

from evidencedesk.db import connection
from evidencedesk.ingest import seed


def migrate() -> None:
    with connection(migration=True) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1000)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.evidencedesk_migrations "
            "(name text PRIMARY KEY, hash text NOT NULL)"
        )
        for path in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
            text = path.read_text()
            digest = hashlib.sha256(text.encode()).hexdigest()
            row = conn.execute(
                "SELECT hash FROM public.evidencedesk_migrations WHERE name=%s", (path.name,)
            ).fetchone()
            if row:
                if row["hash"] != digest:
                    raise ValueError("Applied migration checksum changed")
                continue
            conn.execute(cast(LiteralString, text))
            conn.execute(
                "INSERT INTO public.evidencedesk_migrations VALUES(%s,%s)", (path.name, digest)
            )
            print("Applied", path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="EvidenceDesk maintenance (never runs on startup)")
    parser.add_argument(
        "command", choices=["migrate", "seed", "ingest-live", "provider-smoke", "cleanup"]
    )
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--smoke-receipt", type=Path)
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
    elif args.command == "seed":
        print("Changed fixture chunks:", seed())
    elif args.command == "ingest-live":
        from evidencedesk.live_ingest import ingest_live

        print(
            "Live chunks embedded:",
            ingest_live(allow_production=args.allow_production, smoke_receipt=args.smoke_receipt),
        )
    elif args.command == "provider-smoke":
        from evidencedesk.smoke import provider_smoke

        provider_smoke()
        print("Provider smoke receipt saved; human review pending.")
    else:
        with connection(migration=True) as conn:
            rows = conn.execute(
                "DELETE FROM evidence.sessions WHERE id IN "
                "(SELECT id FROM evidence.sessions WHERE expires_at < now() "
                "ORDER BY expires_at LIMIT 100) RETURNING id"
            ).fetchall()
            conn.execute(
                "DELETE FROM evidence.usage_counters WHERE key IN "
                "(SELECT key FROM evidence.usage_counters WHERE expires_at < now() LIMIT 100)"
            )
        print("Expired sessions removed:", len(rows))


if __name__ == "__main__":
    main()
