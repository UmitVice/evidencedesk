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
   └─► LoRA GGUF / merged GGUF ─► llama.cpp ─► EvidenceDesk API (OpenAI-compatible provider)
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

# 4. Train
uv run --project ml python -m evidencedesk_ml.train_mlx --base ~/models/gemma-4-12b-it-qat-mlx-q4 \
  --data ml/data/sft --out ml/artifacts/lora

# 5. Export for transformers (PEFT) and llama.cpp (LoRA GGUF)
uv run --project ml python -m evidencedesk_ml.export_adapter peft --adapter ml/artifacts/lora --out ml/artifacts/peft
python ~/src/llama.cpp/convert_lora_to_gguf.py ml/artifacts/peft --base ~/models/gemma-4-12b-it-qat-unquantized \
  --outfile ml/artifacts/evidencedesk-lora-f16.gguf

# 6. Serve and evaluate
llama-server -m gemma-4-12B-it-qat-UD-Q4_K_XL.gguf --lora ml/artifacts/evidencedesk-lora-f16.gguf --port 8080 --jinja --cache-ram 0
```

Run the API against it with `GENERATION_PROVIDER=openai_compatible` and
`GENERATION_BASE_URL=http://127.0.0.1:8080/v1` (see `.env.example`). `train_unsloth.py` holds
the same recipe for CUDA machines.
