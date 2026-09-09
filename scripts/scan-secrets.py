"""Scan tracked content and reachable history without printing matched secret material."""
import re
import subprocess
import sys

patterns = [
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}",
    rb"(?:sk_live_|AKIA)[A-Za-z0-9]{16,}",
    rb"postgres(?:ql)?://[^\s:/]+:(?!local-development-only)[^\s@]{12,}@",
]
objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"]).splitlines()
files = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
failed = False
for line in objects:
    oid, _, name = line.partition(b" ")
    if not name:
        continue
    kind = subprocess.check_output(["git", "cat-file", "-t", oid]).strip()
    if kind != b"blob":
        continue
    content = subprocess.check_output(["git", "cat-file", "blob", oid])
    if any(re.search(p, content) for p in patterns):
        print("Potential secret in history:", name.decode())
        failed = True
for name in files:
    if not name:
        continue
    with open(name, "rb") as f:
        content = f.read()
    if any(re.search(p, content) for p in patterns):
        print("Potential secret in tracked file:", name.decode())
        failed = True
sys.exit(1 if failed else 0)
