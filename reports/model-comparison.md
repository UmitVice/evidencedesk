# Model comparison: Cloudflare Llama 3.1 8B vs Gemma 4 12B vs EvidenceDesk fine-tune

Prompt `support-v4`. Local runs: llama.cpp on an Apple M5 Pro (24 GB), one request at a
time, grammar-constrained JSON unless marked otherwise. Human semantic review is still
pending; every rate below comes from the production validators.

## RelayNest regression set (40 cases, 30 model generations)

| Model | Schema valid | Citations valid | Status accuracy | End-to-end | p50 | p95 | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cloudflare `llama-3.1-8b-instruct-fast` | 0.933 | 0.933 | 0.800 | 0.800 | 1.7 s | 3.1 s | 5,235 |
| Gemma 4 12B QAT, Q4_0 (base) | 1.000 | 0.967 | 0.867 | 0.867 | 7.1 s | 22.3 s | 5,251 |
| **EvidenceDesk Gemma 4 12B, Q4_0 (fine-tuned)** | **1.000** | **0.967** | **0.900** | **0.900** | **2.6 s** | **6.1 s** | **2,199** |

Latency includes live embedding, three retrieval methods, and generation. Cloudflare runs on
data-center GPUs; both Gemma rows run on a laptop.

## Held-out products (104 prompts, never seen in training)

FlagForge (English) and Fatura Bulutu (Turkish).

| Model | Pass rate | English | Turkish | Obsolete vs current | Unresolved policy | Without grammar | p50 | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 12B QAT Q4_0 (base) | 0.942 | 0.953 | 0.925 | 0.875 | 0.333 | 0.269 | 10.5 s | 244 |
| **Fine-tuned Q4_0** | **0.971** | **0.969** | **0.975** | **1.000** | **0.667** | **0.904** | **6.1 s** | **109** |

"Without grammar" is the pass rate when the server does not enforce the JSON schema. The base
model mostly wraps JSON in prose or code fences; the fine-tune emits the contract on its own.

## What changed along the way

1. **Prompt bug, all models.** `json.dumps` escaped non-ASCII evidence (`ş`), so models
   had to decode escapes to quote verbatim. Fixing it (`support-v4`) lifted the base model on
   Turkish held-out prompts from 0.625 to 0.925, cut Turkish prompt length by up to 43%, and
   is a production fix independent of fine-tuning.
2. **First adapter (support-v3, 2 epochs, stopped by Metal OOM).** Validation loss plateaued
   after epoch 1 while training loss kept falling, so the epoch-1 checkpoint was kept. It was
   faster but lost to the base model on Turkish citations, which led to finding the bug above.
3. **Runtime LoRA vs merged weights.** Applying the second adapter as a LoRA GGUF on top of
   Unsloth's UD-Q4_K_XL quant flipped its first token to prose, although MLX produced JSON from
   the same tokens. The adapter was trained against MLX 4-bit weights of the QAT checkpoint, so
   it is now merged into the QAT bf16 weights and quantized to Q4_0, the format QAT targets.

Earlier runs are kept in `reports/history/model-iterations/` and `reports/heldout/history/`.

## Limits

- 40 regression cases and 104 held-out prompts are small samples. One case is about 3 points
  on RelayNest and 1 point on the held-out set.
- The behavior slices are tiny: 8 obsolete-vs-current and 6 unresolved-policy prompts.
- Held-out labels come from the data recipe and are not human-reviewed.
- Citation integrity is not semantic correctness.
- Both RelayNest obsolete-vs-current cases still fail for both Gemma models.
