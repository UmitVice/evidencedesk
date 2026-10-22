"""Start a local PostgreSQL 16 + pgvector server without Docker, for evaluations.

Run with Python 3.12 (pgserver ships wheels up to 3.12):

    uv run --python 3.12 --with pgserver==0.1.4 scripts/local-pgserver.py

The data directory lives in the ignored .local/ folder and the server keeps running after
this script exits. It prints connection URLs for the evaluation database only; the server
listens on a Unix socket, never on a network port.
"""

import sys
from pathlib import Path

import pgserver

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".local" / "pgserver"
DATABASES = ("evidencedesk_eval",)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(DATA, cleanup_mode=None)
    for name in DATABASES:
        exists = server.psql(f"SELECT 1 FROM pg_database WHERE datname = '{name}';")
        if "1 row" not in exists:
            server.psql(f"CREATE DATABASE {name};")
        print(f"{name}: {server.get_uri(name)}")
    if "--stop" in sys.argv:
        server.cleanup()


if __name__ == "__main__":
    main()
