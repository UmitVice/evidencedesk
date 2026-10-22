---
title: EvidenceDesk
emoji: 🧾
colorFrom: indigo
colorTo: green
sdk: gradio
sdk_version: 6.30.0
python_version: "3.12"
app_file: app.py
pinned: true
license: mit
short_description: Cited support answers from a fine-tuned Gemma 4 12B
models:
  - google/gemma-4-12B-it-qat-q4_0-unquantized
  - BAAI/bge-small-en-v1.5
tags:
  - rag
  - gemma
  - lora
  - evaluation
  - zerogpu
preload_from_hub:
  - google/gemma-4-12B-it-qat-q4_0-unquantized
  - BAAI/bge-small-en-v1.5
---

# EvidenceDesk

A support copilot that answers only from retrieved documentation, cites verbatim quotes,
abstains when the evidence is missing, and can only propose an internal note that a human must
approve. Source code: [github.com/UmitVice/evidencedesk](https://github.com/UmitVice/evidencedesk).

This Space runs the same Python package as the production API, with free, self-contained
infrastructure: PostgreSQL + pgvector from `pgserver`, bge-small embeddings on CPU, and a
fine-tuned Gemma 4 12B on ZeroGPU. Sandbox data resets when the Space restarts.
