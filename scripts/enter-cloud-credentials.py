"""Collect missing cloud credentials in a real terminal without echoing values."""
import getpass
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".local/private"


def secure_write(path: Path, text: str) -> None:
    if path.is_symlink():
        raise ValueError("Refusing a symbolic-link credential file")
    if subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=ROOT, check=False
    ).returncode:
        raise ValueError("Credential destination must be ignored by Git")
    fd, temporary = tempfile.mkstemp(prefix=".env-credential-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Run this command directly in an interactive terminal")
    warnings.simplefilter("error", getpass.GetPassWarning)
    if PRIVATE.is_symlink():
        raise ValueError("Refusing a symbolic-link private directory")
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    PRIVATE.chmod(0o700)
    password = getpass.getpass("Supabase database password (Enter to preserve/skip): ")
    token = getpass.getpass("Cloudflare Workers AI token (Enter to preserve/skip): ")
    if password and (len(password) < 12 or any(ord(c) < 32 for c in password)):
        raise ValueError("Database password must contain at least 12 printable characters")
    if token and not re.fullmatch(r"[A-Za-z0-9_-]{30,200}", token):
        raise ValueError("Cloudflare token format is invalid")
    if password:
        # Connection metadata is verified separately before constructing any DSN.
        secure_write(PRIVATE / "database-credential.json", json.dumps({"password": password}))
        print("Database password stored securely; connection metadata still requires verification.")
    if token:
        env = ROOT / ".env"
        if env.is_symlink():
            raise ValueError("Refusing a symbolic-link environment file")
        lines = env.read_text().splitlines() if env.exists() else []
        lines = [line for line in lines if not line.startswith("CLOUDFLARE_API_TOKEN=")]
        lines.append("CLOUDFLARE_API_TOKEN=" + token)
        secure_write(env, "\n".join(lines) + "\n")
        print("CLOUDFLARE_API_TOKEN configured.")
    print("Credential entry complete. No values were displayed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Credential entry was not completed; check the terminal and ignored file permissions.")
        sys.exit(1)
