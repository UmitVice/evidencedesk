---
license: apache-2.0
base_model: google/gemma-4-12B-it-qat-q4_0-unquantized
library_name: peft
pipeline_tag: text-generation
language:
  - en
  - tr
tags:
  - lora
  - peft
  - mlx
  - gemma4
  - rag
  - grounded-generation
  - citations
  - distillation
datasets:
  - UmitVice/evidencedesk-grounded-support
---

# EvidenceDesk Gemma 4 12B (LoRA)

A LoRA adapter that teaches Gemma 4 12B the EvidenceDesk answer contract:

- answer only from the supplied passages;
- cite every claim with a verbatim quote and the passage ID;
- abstain with `insufficient_evidence` when evidence is missing, unresolved, or about another
  customer;
- ignore instructions injected into tickets or documents;
- emit compact strict JSON.

The base is Google's QAT checkpoint, so the merged model stays accurate at 4-bit.

- Demo: [UmitVice/evidencedesk Space](https://huggingface.co/spaces/UmitVice/evidencedesk) (free ZeroGPU)
- Merged 4-bit GGUF for llama.cpp, Ollama, LM Studio: [UmitVice/evidencedesk-gemma-4-12b-GGUF](https://huggingface.co/UmitVice/evidencedesk-gemma-4-12b-GGUF)
- Training data: [UmitVice/evidencedesk-grounded-support](https://huggingface.co/datasets/UmitVice/evidencedesk-grounded-support)
- Code, prompt, validators, and evaluation: [github.com/UmitVice/evidencedesk](https://github.com/UmitVice/evidencedesk)

## Results

Prompt `support-v4`, llama.cpp on an Apple M5 Pro, merged Q4_0 vs the same pipeline without
the adapter.

| | Cloudflare Llama 3.1 8B | Gemma 4 12B QAT Q4_0 | **This model, Q4_0** |
| --- | --- | --- | --- |
| RelayNest end-to-end pass (30 generations) | 0.800 | 0.867 | **0.900** |
| RelayNest latency p50 / p95 | 1.7 s / 3.1 s (cloud GPU) | 7.1 s / 22.3 s | **2.6 s / 6.1 s** |
| Held-out products pass (104) | – | 0.942 | **0.971** |
| Held-out Turkish | – | 0.925 | **0.975** |
| Held-out without grammar-constrained decoding | – | 0.269 | **0.904** |
| Mean output tokens | – | 244 | **109** |

The held-out products (FlagForge, Fatura Bulutu) and RelayNest were never in the training
data. Full tables and the history of failed iterations are in `reports/`.

## Files

| Path | Use |
| --- | --- |
| `adapter_model.safetensors`, `adapter_config.json` | PEFT LoRA for transformers |
| `mlx/` | the original MLX adapter (`mlx_lm.load(base, adapter_path="mlx")`) |
| `reports/` | evaluation reports |

The adapter targets the attention and MLP projections of all 48 text layers (rank 16,
alpha 32). It was trained against MLX 4-bit weights; for 4-bit serving, merge it into the
bf16 base and then quantize, as the GGUF repo does. Applying it as a runtime LoRA on a
different 4-bit quant can change its behavior.

## Usage (transformers)

```python
import torch
from peft import PeftModel
from transformers import AutoTokenizer, Gemma4UnifiedForConditionalGeneration

base = "google/gemma-4-12B-it-qat-q4_0-unquantized"
tokenizer = AutoTokenizer.from_pretrained(base)
model = Gemma4UnifiedForConditionalGeneration.from_pretrained(base, dtype=torch.bfloat16)
model = PeftModel.from_pretrained(model, "UmitVice/evidencedesk-gemma-4-12b-lora").merge_and_unload()
```

Render prompts with EvidenceDesk's `build_messages()` (system prompt, JSON schema, ticket,
question, evidence) and `apply_chat_template(..., add_generation_prompt=True)`.

## Training

- **Data.** 514 training and 104 validation examples, distilled from Gemma 4 26B-A4B on ten
  fictional products. They were filtered with the production validators: strict schema,
  citations to retrieved passages, verbatim quotes, and the expected answer status.
- **Method.** QLoRA with MLX on a 24 GB Apple M5 Pro: 1 epoch, learning rate 1e-4 with
  cosine decay and 15 warmup steps, effective batch 8, max length 4,096. Loss covers only the
  answer, and prompts are rendered exactly as served, including Gemma 4's empty thought
  channel.
- **Training cost.** About 1.5 hours and no paid compute.

## Limitations

- The evaluation sets are small: 40 regression cases and 104 held-out prompts.
- The labels are automatic, not human-reviewed.
- A valid citation does not prove the answer is semantically correct.
- The two RelayNest "compare current with legacy" cases still fail.
- The model is tuned for the EvidenceDesk prompt and schema; it is not a general chat model.
- A human approves every proposed note before anything is saved.
