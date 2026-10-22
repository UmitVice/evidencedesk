"""LoRA fine-tuning of Gemma 4 on Apple Silicon with MLX (QLoRA on a 4-bit base).

Recipe mirrors the usual Unsloth QLoRA setup (rank 16, alpha 32, all attention and MLP
projections, response-only loss, cosine schedule with warmup) so the same hyperparameters
transfer to `train_unsloth.py` on CUDA.

Examples are rendered with the exact serving prompt: the chat template with
`add_generation_prompt=True` (which for Gemma 4 ends in an empty thought channel) followed by
the compact JSON answer and the end-of-turn token. Loss is computed on the answer only.
"""

import argparse
import json
import math
import time
from pathlib import Path

import mlx.core as mx
import mlx.optimizers as optim
from mlx_lm import load
from mlx_lm.tuner.datasets import CacheDataset
from mlx_lm.tuner.trainer import TrainingArgs, TrainingCallback, train
from mlx_lm.tuner.utils import linear_to_lora_layers, print_trainable_parameters

END_OF_TURN = "<turn|>"
LORA_KEYS = [
    "self_attn.q_proj",
    "self_attn.k_proj",
    "self_attn.v_proj",
    "self_attn.o_proj",
    "mlp.gate_proj",
    "mlp.up_proj",
    "mlp.down_proj",
]


class RenderedDataset:
    """Pre-tokenized (tokens, prompt_length) pairs consumed by the mlx-lm trainer."""

    def __init__(self, path: Path, tokenizer, max_seq_length: int):
        self.items: list[tuple[list[int], int]] = []
        self.skipped = 0
        for line in path.read_text().splitlines():
            messages = json.loads(line)["messages"]
            prompt = tokenizer.apply_chat_template(
                messages[:-1], add_generation_prompt=True, tokenize=False
            )
            completion = messages[-1]["content"] + END_OF_TURN
            prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
            completion_ids = tokenizer.encode(completion, add_special_tokens=False)
            tokens = prompt_ids + completion_ids
            if len(tokens) > max_seq_length:
                self.skipped += 1
                continue
            self.items.append((tokens, len(prompt_ids)))

    def process(self, item):
        return item

    def __getitem__(self, index: int):
        return self.items[index]

    def __len__(self) -> int:
        return len(self.items)


class JsonlLogger(TrainingCallback):
    def __init__(self, path: Path):
        self.path = path
        self.started = time.time()

    def _write(self, record: dict) -> None:
        record["elapsed_s"] = round(time.time() - self.started, 1)
        with self.path.open("a") as handle:
            handle.write(json.dumps(record) + "\n")

    def on_train_loss_report(self, info: dict) -> None:
        self._write({"type": "train", **{k: float(v) for k, v in info.items()}})

    def on_val_loss_report(self, info: dict) -> None:
        self._write({"type": "val", **{k: float(v) for k, v in info.items()}})


def schedule(lr: float, warmup: int, total: int):
    warm = optim.linear_schedule(lr * 0.01, lr, max(warmup, 1))
    decay = optim.cosine_decay(lr, max(total - warmup, 1), lr * 0.1)
    return optim.join_schedules([warm, decay], [max(warmup, 1)])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="MLX model directory (4-bit)")
    parser.add_argument("--data", type=Path, required=True, help="Directory with train/valid.jsonl")
    parser.add_argument("--out", type=Path, required=True, help="Adapter output directory")
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--alpha", type=float, default=32)
    parser.add_argument("--dropout", type=float, default=0.05)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--epochs", type=float, default=2)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=3072)
    parser.add_argument("--warmup-steps", type=int, default=15, help="Optimizer steps")
    parser.add_argument("--num-layers", type=int, default=-1, help="-1 means every block")
    parser.add_argument("--val-batches", type=int, default=40)
    parser.add_argument("--steps-per-eval", type=int, default=200)
    parser.add_argument("--max-iters", type=int, default=0, help="Override for smoke tests")
    parser.add_argument("--no-grad-checkpoint", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    mx.random.seed(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    model, tokenizer = load(args.base)
    train_set = RenderedDataset(args.data / "train.jsonl", tokenizer, args.max_seq_length)
    valid_set = RenderedDataset(args.data / "valid.jsonl", tokenizer, args.max_seq_length)
    lengths = sorted(len(t) for t, _ in train_set.items)
    print(
        f"train={len(train_set)} valid={len(valid_set)} skipped_long="
        f"{train_set.skipped + valid_set.skipped} median_tokens={lengths[len(lengths) // 2]} "
        f"max_tokens={lengths[-1]}"
    )

    num_layers = len(model.layers) if args.num_layers < 0 else args.num_layers
    lora = {
        "rank": args.rank,
        "scale": args.alpha / args.rank,
        "dropout": args.dropout,
        "keys": LORA_KEYS,
    }
    model.freeze()
    linear_to_lora_layers(model, num_layers, lora)
    print_trainable_parameters(model)

    iters = args.max_iters or math.ceil(len(train_set) * args.epochs / args.batch_size)
    optimizer_steps = max(iters // args.grad_accum, 1)
    optimizer = optim.AdamW(
        learning_rate=schedule(args.lr, args.warmup_steps, optimizer_steps), weight_decay=0.0
    )
    config = {
        "fine_tune_type": "lora",
        "num_layers": num_layers,
        "lora_parameters": lora,
        "base_model": str(args.base),
        "recipe": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "iters": iters,
        "optimizer_steps": optimizer_steps,
        "train_examples": len(train_set),
        "valid_examples": len(valid_set),
    }
    (args.out / "adapter_config.json").write_text(json.dumps(config, indent=2) + "\n")
    training_args = TrainingArgs(
        batch_size=args.batch_size,
        iters=iters,
        val_batches=args.val_batches,
        steps_per_report=10,
        steps_per_eval=args.steps_per_eval,
        steps_per_save=args.steps_per_eval,
        max_seq_length=args.max_seq_length,
        adapter_file=str(args.out / "adapters.safetensors"),
        grad_checkpoint=not args.no_grad_checkpoint,
        grad_accumulation_steps=args.grad_accum,
    )
    train(
        model=model,
        optimizer=optimizer,
        train_dataset=CacheDataset(train_set),
        val_dataset=CacheDataset(valid_set),
        args=training_args,
        training_callback=JsonlLogger(args.out / "metrics.jsonl"),
    )
    print(f"Adapters saved to {args.out}")


if __name__ == "__main__":
    main()
