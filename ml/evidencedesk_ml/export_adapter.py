"""Export an MLX LoRA adapter for serving outside MLX.

    peft  MLX adapter -> PEFT adapter (transformers on ZeroGPU, llama.cpp convert_lora_to_gguf)
    fuse  MLX adapter + bf16 Hugging Face base -> fused bf16 checkpoint (for a merged GGUF)

MLX LoRA computes y = W x + scale * (x @ A) @ B with A: (in, r) and B: (r, out). PEFT computes
y = W x + (alpha / r) * B' (A' x) with A': (r, in) and B': (out, r), so A' = A.T, B' = B.T and
alpha = scale * r. MLX names Gemma 4 text layers `language_model.model.layers.N...`; the
Hugging Face checkpoint names them `model.language_model.layers.N...`.
"""

import argparse
import json
import shutil
from pathlib import Path

import mlx.core as mx
from safetensors import safe_open

MLX_PREFIX = "language_model.model."
HF_PREFIX = "model.language_model."


def hf_module(mlx_module: str) -> str:
    if not mlx_module.startswith(MLX_PREFIX):
        raise ValueError(f"Unexpected adapter module: {mlx_module}")
    return HF_PREFIX + mlx_module.removeprefix(MLX_PREFIX)


def load_adapter(adapter_dir: Path) -> tuple[dict[str, tuple[mx.array, mx.array]], dict]:
    config = json.loads((adapter_dir / "adapter_config.json").read_text())
    weights = mx.load(str(adapter_dir / "adapters.safetensors"))
    modules: dict[str, tuple[mx.array, mx.array]] = {}
    for key in weights:
        if key.endswith(".lora_a"):
            module = key.removesuffix(".lora_a")
            modules[hf_module(module)] = (weights[key], weights[module + ".lora_b"])
    if not modules:
        raise ValueError("No LoRA weights found")
    return modules, config


def export_peft(adapter_dir: Path, out: Path, base_model: str) -> None:
    modules, config = load_adapter(adapter_dir)
    lora = config["lora_parameters"]
    rank = int(lora["rank"])
    tensors: dict[str, mx.array] = {}
    for module, (a, b) in modules.items():
        tensors[f"base_model.model.{module}.lora_A.weight"] = a.T.astype(mx.float32)
        tensors[f"base_model.model.{module}.lora_B.weight"] = b.T.astype(mx.float32)
    out.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(str(out / "adapter_model.safetensors"), tensors, {"format": "pt"})
    peft_config = {
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM",
        "base_model_name_or_path": base_model,
        "r": rank,
        "lora_alpha": float(lora["scale"]) * rank,
        "lora_dropout": float(lora["dropout"]),
        "target_modules": sorted(modules),
        "bias": "none",
        "fan_in_fan_out": False,
        "use_rslora": False,
        "inference_mode": True,
        "modules_to_save": None,
    }
    (out / "adapter_config.json").write_text(json.dumps(peft_config, indent=2) + "\n")
    print(f"PEFT adapter with {len(modules)} modules written to {out}")


def fuse(adapter_dir: Path, base_dir: Path, out: Path, shard_bytes: int = 4 << 30) -> None:
    """Stream the base checkpoint tensor by tensor, so peak memory stays near one shard."""
    modules, config = load_adapter(adapter_dir)
    scale = float(config["lora_parameters"]["scale"])
    out.mkdir(parents=True, exist_ok=True)
    for item in base_dir.iterdir():
        skip = item.suffix == ".safetensors" or item.name.endswith(".index.json")
        if item.is_file() and not skip:
            shutil.copy2(item, out / item.name)
    sources = sorted(base_dir.glob("*.safetensors"))
    shard: dict[str, mx.array] = {}
    size, index, weight_map, fused = 0, 1, {}, 0

    def flush() -> None:
        nonlocal shard, size, index
        if not shard:
            return
        name = f"model-{index:05d}.safetensors"
        mx.save_safetensors(str(out / name), shard, {"format": "pt"})
        weight_map.update({key: name for key in shard})
        shard, size, index = {}, 0, index + 1

    for source in sources:
        with safe_open(str(source), framework="mlx") as handle:
            for key in handle.keys():
                tensor = handle.get_tensor(key)
                module = key.removesuffix(".weight")
                if key.endswith(".weight") and module in modules:
                    a, b = modules[module]
                    delta = (scale * (a.astype(mx.float32) @ b.astype(mx.float32))).T
                    tensor = (tensor.astype(mx.float32) + delta).astype(tensor.dtype)
                    fused += 1
                mx.eval(tensor)
                shard[key] = tensor
                size += tensor.nbytes
                if size >= shard_bytes:
                    flush()
    flush()
    if fused != len(modules):
        raise ValueError(f"Fused {fused} of {len(modules)} adapter modules")
    (out / "model.safetensors.index.json").write_text(
        json.dumps({"metadata": {}, "weight_map": weight_map}, indent=2) + "\n"
    )
    print(f"Fused {fused} modules into {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["peft", "fuse"])
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-dir", type=Path, help="bf16 Hugging Face checkpoint for fuse")
    parser.add_argument("--base-model", default="google/gemma-4-12B-it-qat-q4_0-unquantized")
    args = parser.parse_args()
    if args.command == "peft":
        export_peft(args.adapter, args.out, args.base_model)
    else:
        if not args.base_dir:
            parser.error("--base-dir is required for fuse")
        fuse(args.adapter, args.base_dir, args.out)


if __name__ == "__main__":
    main()
