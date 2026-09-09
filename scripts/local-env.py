"""Create local-only environment files without logging generated credentials."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    raise SystemExit(".env exists; preserving it")
key = secrets.token_hex(32)
url = os.environ.get("LOCAL_DATABASE_URL",
                     "postgresql://evidencedesk:local-development-only@127.0.0.1:54329/evidencedesk")
path.write_text(f"ENVIRONMENT=development\nDATABASE_URL={url}\nMIGRATION_DATABASE_URL={url}\n"
                f"SERVICE_KEY={key}\nAI_MODE=simulated\n")
path.chmod(0o600)
web = root / "apps/web/.env.local"
if web.exists():
    raise SystemExit("API env created; existing web env preserved")
web.write_text(f"API_ORIGIN=http://127.0.0.1:8000\nAPP_ORIGIN=http://localhost:3000\nSERVICE_KEY={key}\n")
web.chmod(0o600)
print("Local environment files created. Credentials were not printed.")
