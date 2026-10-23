"""Publish the dataset, LoRA adapter, Space, and collection to the logged-in Hugging Face account.

    hf auth login
    uv run --project ml python scripts/publish_hf.py

Repositories are created under the authenticated user. Nothing secret is uploaded: only the
synthetic dataset, adapter weights, model and dataset cards, and evaluation reports.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "ml"
CARDS = ML / "cards"
DATASET = "evidencedesk-grounded-support"
MODEL = "evidencedesk-gemma-4-12b-lora"
GGUF = "evidencedesk-gemma-4-12b-GGUF"
SPACE = "evidencedesk"


def stage_dataset(target: Path) -> None:
    data = ML / "data"
    (target / "data").mkdir(parents=True)
    for name in ("train.jsonl", "valid.jsonl", "train.meta.jsonl", "valid.meta.jsonl"):
        shutil.copy2(data / "sft" / name, target / "data" / name)
    shutil.copytree(data / "corpus", target / "corpus")
    shutil.copy2(data / "build-report.json", target / "build-report.json")
    shutil.copy2(CARDS / "dataset.md", target / "README.md")


def stage_model(target: Path, checkpoint: str) -> None:
    """PEFT adapter at the root (transformers / ZeroGPU), MLX adapter under mlx/."""
    artifacts = ML / "artifacts"
    shutil.copytree(artifacts / f"peft-{checkpoint}", target, dirs_exist_ok=True)
    (target / "mlx").mkdir()
    for name in ("adapters.safetensors", "adapter_config.json"):
        shutil.copy2(artifacts / f"ckpt-{checkpoint}" / name, target / "mlx" / name)
    reports = target / "reports"
    reports.mkdir()
    names = ("model-comparison.md", "final-finetuned.md", "final-base.md", "final-cloudflare.md")
    for name in names:
        shutil.copy2(ROOT / "reports" / name, reports / name)
    shutil.copytree(ROOT / "reports" / "heldout", reports / "heldout",
                    ignore=shutil.ignore_patterns("history"))
    shutil.copy2(CARDS / "model.md", target / "README.md")


def stage_gguf(target: Path) -> None:
    target.mkdir(parents=True)
    shutil.copy2(CARDS / "gguf.md", target / "README.md")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="v4")
    parser.add_argument("--skip-gguf", action="store_true")
    parser.add_argument("--skip-space", action="store_true")
    args = parser.parse_args()

    api = HfApi()
    owner = api.whoami()["name"]
    dataset_id, model_id, gguf_id, space_id = (
        f"{owner}/{n}" for n in (DATASET, MODEL, GGUF, SPACE)
    )

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "dataset"
        stage_dataset(staged)
        api.create_repo(dataset_id, repo_type="dataset", exist_ok=True)
        api.upload_folder(repo_id=dataset_id, repo_type="dataset", folder_path=str(staged),
                          commit_message="Publish EvidenceDesk grounded-support SFT data")
        print("dataset:", f"https://huggingface.co/datasets/{dataset_id}")

        staged = Path(tmp) / "model"
        stage_model(staged, args.checkpoint)
        api.create_repo(model_id, exist_ok=True)
        api.upload_folder(repo_id=model_id, folder_path=str(staged),
                          commit_message=f"Publish LoRA checkpoint {args.checkpoint}")
        print("model:", f"https://huggingface.co/{model_id}")

        if not args.skip_gguf:
            staged = Path(tmp) / "gguf"
            stage_gguf(staged)
            api.create_repo(gguf_id, exist_ok=True)
            api.upload_folder(repo_id=gguf_id, folder_path=str(staged),
                              commit_message="Add model card")
            api.upload_file(
                path_or_fileobj=str(ML / "artifacts" / "evidencedesk-gemma-4-12b-Q4_0.gguf"),
                path_in_repo="evidencedesk-gemma-4-12b-Q4_0.gguf",
                repo_id=gguf_id,
                commit_message="Add merged Q4_0 GGUF",
            )
            print("gguf:", f"https://huggingface.co/{gguf_id}")

    if not args.skip_space:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "deploy_space.py"), "--repo", space_id,
             "--adapter-repo", model_id],
            check=True,
        )

    collection = api.create_collection(
        title="EvidenceDesk: grounded support answers",
        namespace=owner,
        description="Distilled SFT data, a Gemma 4 12B LoRA adapter, and a free ZeroGPU demo.",
        exists_ok=True,
    )
    items: list[tuple[str, Literal["space", "model", "dataset"]]] = [
        (space_id, "space"), (model_id, "model"), (gguf_id, "model"), (dataset_id, "dataset")
    ]
    for item_id, item_type in items:
        skipped_space = item_type == "space" and args.skip_space
        if skipped_space or (item_id == gguf_id and args.skip_gguf):
            continue
        api.add_collection_item(collection.slug, item_id, item_type, exists_ok=True)
    print("collection:", f"https://huggingface.co/collections/{collection.slug}")


if __name__ == "__main__":
    main()
