# EvidenceDesk model work

Distill a grounded-answer behavior from Gemma 4 26B-A4B into Gemma 4 12B, train a LoRA adapter
on Apple Silicon, and serve it through llama.cpp locally or transformers on a free Hugging Face
ZeroGPU Space. Everything runs on one 24 GB Mac; nothing here needs a paid service.

```
teacher (Gemma 4 26B-A4B QAT Q4, llama.cpp)
   │  grammar-constrained JSON, production prompt
   ▼
synthetic help centers ──► tickets ──► BM25 context ──► teacher answer ──► production validators
(10 fictional products,                                                     │ keep only valid answers
 2 Turkish, 2 held out)                                                     ▼ with the expected status
                                                    SFT data (prompt + compact JSON answer)
                                                                            │
student (Gemma 4 12B QAT, MLX 4-bit) ◄── LoRA r16, answer-only loss ────────┘
   │
   ├─► PEFT adapter ─► ZeroGPU Space (transformers, bf16 QAT base)
   └─► merge into QAT bf16 ─► GGUF ─► Q4_0 ─► llama.cpp ─► EvidenceDesk API
```

## Why these choices

- **Fine-tune, not pre-train.** The goal is a narrow behavior: cite verbatim, abstain instead of
  guessing, ignore injected instructions, and emit strict JSON. LoRA on a strong instruction
  model is the cheapest way to get it.
- **QAT base.** `google/gemma-4-12B-it-qat-q4_0-unquantized` was trained to survive 4-bit
  quantization, so the adapter is trained and served against weights that stay close to the
  Q4 model that actually runs.
- **No eval leakage.** Training data comes from ten fictional products. RelayNest, the product
  in the 40-case evaluation set, is never used, and an 8-gram overlap check guards the questions.
- **No train/serve skew.** Prompts are rendered with the API's `build_messages()` and the model's
  chat template with `add_generation_prompt=True`, which for Gemma 4 ends in an empty thought
  channel. The target is the canonical compact JSON plus the end-of-turn token.
- **Validators as the filter.** Teacher answers are kept only if they pass the same schema,
  citation, and verbatim-quote checks as production and match the expected answer status.

## Commands

```bash
# 0. Environment (Python 3.13, MLX)
uv sync --project ml

# 1. Teacher server (single slot; the host prompt cache would copy ~4 GB per request)
llama-server -m gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf --port 8081 -c 8192 -np 1 --jinja --cache-ram 0

# 2. Data: corpus -> tickets -> answers -> export (resumable)
PYTHONPATH=ml apps/api/.venv/bin/python -m evidencedesk_ml.dataset all --teacher-url http://127.0.0.1:8081/v1

# 3. Student base: QAT bf16 -> MLX 4-bit (group size 32 matches Q4_0 blocks)
uv run --project ml mlx_lm.convert --hf-path ~/models/gemma-4-12b-it-qat-unquantized \
  --mlx-path ~/models/gemma-4-12b-it-qat-mlx-q4 -q --q-bits 4 --q-group-size 32

# 4. Train (1 epoch; validation loss plateaued after epoch 1 in the first run)
uv run --project ml python -m evidencedesk_ml.train_mlx --base ~/models/gemma-4-12b-it-qat-mlx-q4 \
  --data ml/data/sft --out ml/artifacts/lora --epochs 1 --max-seq-length 4096

# 5. Export: PEFT for transformers, and a merged Q4_0 GGUF for llama.cpp
uv run --project ml python -m evidencedesk_ml.export_adapter peft --adapter ml/artifacts/lora --out ml/artifacts/peft
uv run --project ml python -m evidencedesk_ml.export_adapter fuse --adapter ml/artifacts/lora \
  --base-dir ~/models/gemma-4-12b-it-qat-unquantized --out ml/artifacts/fused
python ml/scripts/convert_gemma4_gguf.py ~/src/llama.cpp ml/artifacts/fused --outfile fused-bf16.gguf --outtype bf16
llama-quantize fused-bf16.gguf ml/artifacts/evidencedesk-gemma-4-12b-Q4_0.gguf Q4_0

# 6. Serve and evaluate
llama-server -m ml/artifacts/evidencedesk-gemma-4-12b-Q4_0.gguf --port 8080 --jinja --cache-ram 0
PYTHONPATH=ml apps/api/.venv/bin/python -m evidencedesk_ml.eval_heldout --model local --out reports/heldout/run.json
```

Do not apply the adapter as a runtime LoRA on a different 4-bit quant (for example Unsloth's
UD-Q4_K_XL): it was trained against MLX 4-bit weights of the QAT checkpoint, and on another
quant it switched to prose answers. Merging into bf16 and quantizing to Q4_0 matches what QAT
was trained for. See [the comparison report](../reports/model-comparison.md).

Run the API against it with `GENERATION_PROVIDER=openai_compatible` and
`GENERATION_BASE_URL=http://127.0.0.1:8080/v1` (see `.env.example`). `train_unsloth.py` holds
the same recipe for CUDA machines.
