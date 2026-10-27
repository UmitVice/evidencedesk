"""Store an OpenAI API key in the ignored local .env without echoing or printing it."""
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
NAME = "GENERATION_API_KEY"


def main() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Run this command directly in an interactive terminal")
    warnings.simplefilter("error", getpass.GetPassWarning)
    if ENV.is_symlink():
        raise ValueError("Refusing a symbolic-link environment file")
    if subprocess.run(["git", "check-ignore", "-q", str(ENV)], cwd=ROOT, check=False).returncode:
        raise ValueError("The .env file must be ignored by Git")
    key = getpass.getpass("OpenAI API key (input hidden, Enter to cancel): ").strip()
    if not key:
        print("Nothing changed.")
        return
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{20,300}", key):
        raise ValueError("That does not look like an OpenAI API key")
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    lines = [line for line in lines if not line.startswith(NAME + "=")]
    lines.append(f"{NAME}={key}")
    fd, temporary = tempfile.mkstemp(prefix=".env-credential-", dir=ROOT)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write("\n".join(lines) + "\n")
        os.replace(temporary, ENV)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"{NAME} stored in .env (mode 0600, ignored by Git). The key was not displayed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError, KeyboardInterrupt, getpass.GetPassWarning) as exc:
        # Messages above never contain the key.
        raise SystemExit(f"Key entry stopped: {exc or type(exc).__name__}") from None
