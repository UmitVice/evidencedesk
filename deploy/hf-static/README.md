---
title: EvidenceDesk
emoji: 🧾
colorFrom: indigo
colorTo: green
sdk: static
pinned: true
license: mit
short_description: Cited support answers from a fine-tuned Gemma 4 12B
models:
  - UmitVice/evidencedesk-gemma-4-12b-lora
  - UmitVice/evidencedesk-gemma-4-12b-GGUF
datasets:
  - UmitVice/evidencedesk-grounded-support
tags:
  - rag
  - gemma
  - lora
  - evaluation
---

# EvidenceDesk

Recorded runs of the fine-tuned Gemma 4 12B on the EvidenceDesk support copilot, with cited
evidence, abstentions, a known miss, and the evaluation summary. Every run was produced by
`scripts/record_demo.py` through the production retrieval, prompt, and validators.

Source: [github.com/UmitVice/evidencedesk](https://github.com/UmitVice/evidencedesk).
