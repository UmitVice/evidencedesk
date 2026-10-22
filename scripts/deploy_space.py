"""Assemble and publish the Hugging Face ZeroGPU Space.

    uv run --project ml python scripts/deploy_space.py --repo UmitVice/evidencedesk \
        --adapter-repo UmitVice/evidencedesk-gemma-4-12b-lora

Use --out DIR --no-upload to assemble locally for testing. Only source, migrations, the
synthetic corpus, eval cases, and published reports are copied; no environment files.
"""

import argparse
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
SPACE = ROOT / "deploy" / "hf-space"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".env*", ".pytest_cache", ".ruff_cache")


def assemble(target: Path, adapter_repo: str) -> None:
    for name in ("app.py", "requirements.txt", "ABOUT.md"):
        shutil.copy2(SPACE / name, target / name)
    readme = (SPACE / "README.md").read_text()
    if adapter_repo:
        readme = readme.replace(
            "  - BAAI/bge-small-en-v1.5\ntags:",
            f"  - BAAI/bge-small-en-v1.5\n  - {adapter_repo}\ntags:",
            1,
        )
    (target / "README.md").write_text(readme)
    for name in ("evidencedesk", "data", "migrations", "evals"):
        shutil.copytree(API / name, target / name, ignore=IGNORE, dirs_exist_ok=True)
    report = ROOT / "reports" / "model-comparison.md"
    if report.exists():
        (target / "reports").mkdir(exist_ok=True)
        shutil.copy2(report, target / "reports" / report.name)
    leaked = [p for p in target.rglob("*") if p.name.startswith(".env")]
    if leaked:
        raise SystemExit(f"Refusing to publish environment files: {leaked}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="UmitVice/evidencedesk")
    parser.add_argument("--adapter-repo", default="")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args()

    target = args.out or Path(tempfile.mkdtemp(prefix="evidencedesk-space-"))
    target.mkdir(parents=True, exist_ok=True)
    assemble(target, args.adapter_repo)
    print(f"Assembled Space in {target}")
    if args.no_upload:
        return

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(
        args.repo, repo_type="space", space_sdk="gradio", exist_ok=True,
        space_hardware="zero-a10g",
    )
    if args.adapter_repo:
        api.add_space_variable(args.repo, "ADAPTER_REPO", args.adapter_repo)
    api.upload_folder(
        repo_id=args.repo, repo_type="space", folder_path=str(target),
        commit_message="Deploy EvidenceDesk from GitHub", delete_patterns=["*.py", "**/*.py"],
    )
    print(f"https://huggingface.co/spaces/{args.repo}")


if __name__ == "__main__":
    main()
