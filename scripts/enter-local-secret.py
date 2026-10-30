"""Store a local secret in the ignored .env without echoing or printing it.

    python3 scripts/enter-local-secret.py openai           # GENERATION_API_KEY
    python3 scripts/enter-local-secret.py review-database  # REVIEW_DATABASE_URL
"""
import argparse
import getpass
import os
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
SECRETS = {
    "openai": ("GENERATION_API_KEY", "OpenAI API key", r"sk-[A-Za-z0-9_-]{20,300}"),
    # The production runtime connection string (read access is all the report needs).
    "review-database": (
        "REVIEW_DATABASE_URL",
        "PostgreSQL connection string for flagged-analysis reports",
        r"postgres(ql)?://[^\s]{10,500}",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("secret", choices=SECRETS)
    name, label, pattern = SECRETS[parser.parse_args().secret]
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Run this command directly in an interactive terminal")
    warnings.simplefilter("error", getpass.GetPassWarning)
    if ENV.is_symlink():
        raise ValueError("Refusing a symbolic-link environment file")
    if subprocess.run(["git", "check-ignore", "-q", str(ENV)], cwd=ROOT, check=False).returncode:
        raise ValueError("The .env file must be ignored by Git")
    value = getpass.getpass(f"{label} (input hidden, Enter to cancel): ").strip()
    if not value:
        print("Nothing changed.")
        return
    if not re.fullmatch(pattern, value):
        raise ValueError(f"That does not look like a valid {label}")
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    lines = [line for line in lines if not line.startswith(name + "=")]
    lines.append(f"{name}={value}")
    fd, temporary = tempfile.mkstemp(prefix=".env-credential-", dir=ROOT)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write("\n".join(lines) + "\n")
        os.replace(temporary, ENV)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"{name} stored in .env (mode 0600, ignored by Git). The value was not displayed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError, KeyboardInterrupt, getpass.GetPassWarning) as exc:
        # Messages above never contain the secret.
        raise SystemExit(f"Secret entry stopped: {exc or type(exc).__name__}") from None
