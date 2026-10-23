---
license: apache-2.0
base_model: UmitVice/evidencedesk-gemma-4-12b-lora
pipeline_tag: text-generation
language:
  - en
  - tr
tags:
  - gguf
  - llama.cpp
  - gemma4
  - qat
  - rag
  - grounded-generation
---

# EvidenceDesk Gemma 4 12B, Q4_0 GGUF

[UmitVice/evidencedesk-gemma-4-12b-lora](https://huggingface.co/UmitVice/evidencedesk-gemma-4-12b-lora)
merged into `google/gemma-4-12B-it-qat-q4_0-unquantized` in bf16, converted with llama.cpp
b9960, and quantized to **Q4_0**, the format the QAT checkpoint was trained for (7.0 GB).

| | Gemma 4 12B QAT Q4_0 | **This file** |
| --- | --- | --- |
| EvidenceDesk regression set, end-to-end pass | 0.867 | **0.900** |
| p50 / p95 latency on an M5 Pro | 7.1 s / 22.3 s | **2.6 s / 6.1 s** |
| Held-out products, pass rate | 0.942 | **0.971** |
| Mean output tokens | 244 | **109** |

```bash
llama-server -m evidencedesk-gemma-4-12b-Q4_0.gguf --jinja -c 8192 --cache-ram 0 --port 8080
```

Point EvidenceDesk at it with `GENERATION_PROVIDER=openai_compatible` and
`GENERATION_BASE_URL=http://127.0.0.1:8080/v1`. The API sends
`chat_template_kwargs.enable_thinking=false` and a per-request JSON schema whose source IDs are
limited to the retrieved passages. `--cache-ram 0` avoids copying a multi-GB prompt cache after
every request on 24 GB machines.

The model is tuned for the EvidenceDesk prompt (`support-v4`) and schema, not as a general chat
model.
