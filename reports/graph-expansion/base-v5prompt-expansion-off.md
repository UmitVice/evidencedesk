# Live model evaluation

Human review: pending.

Commit: `2029dfc76eb97ffb0e0e350a33eed14244fbd93b`

Mode/split: live / all. Processed: 48/48 cases.
Prompt: `support-v5`. Model: `evidencedesk-gemma-4-12b-lora`.
Embedding: `BAAI/bge-small-en-v1.5` (384 dimensions).
Dataset hash: `428655b5b1c8b43670944e22bd84f830f04c27336f10c76f0d0a414c131919dc`.
Corpus hash: `314a2457d6639c7b813bf9a600cb080b524bf752f162b86bfd73ece02f60d4d3`.
Generation attempts/completions: 38 / 38.

| Retrieval | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| lexical | 24 | 0.9583333333333334 | 0.7326388888888888 |
| vector | 24 | 0.9583333333333334 | 0.8854166666666666 |
| hybrid | 24 | 0.9791666666666666 | 0.9041666666666667 |

| Generation | n | Schema valid | Citations valid | Status accuracy | End-to-end |
| --- | --- | --- | --- | --- | --- |
| evidencedesk-gemma-4-12b-lora | 38 | 1.0 | 1.0 | 0.8684 | 0.8684 |

Served models: {'gemma-4-12b-it-qat-q4': 38}. Tokens: {'prompt_tokens': 51781, 'completion_tokens': 7640}.

Latency n=38: p50 47022.955 ms; p95 77356.1735 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `obsolete-vs-current-1`: expected answer/abstention status disagreed.
- `obsolete-vs-current-2`: expected answer/abstention status disagreed.
- `injection-source-2`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-1`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-2`: expected answer/abstention status disagreed.
- `replay-retention-1`: retrieval miss in vector.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty-eight scenarios are a compact regression corpus, not a market benchmark.
