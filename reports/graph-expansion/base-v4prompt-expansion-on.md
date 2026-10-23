# Live model evaluation

Human review: pending.

Commit: `a2382b47ada3e62ac00d7586f7e4adfd9c3ce1e5`

Mode/split: live / all. Processed: 48/48 cases.
Prompt: `support-v4`. Model: `evidencedesk-gemma-4-12b-lora`.
Embedding: `BAAI/bge-small-en-v1.5` (384 dimensions).
Dataset hash: `428655b5b1c8b43670944e22bd84f830f04c27336f10c76f0d0a414c131919dc`.
Corpus hash: `314a2457d6639c7b813bf9a600cb080b524bf752f162b86bfd73ece02f60d4d3`.
Generation attempts/completions: 38 / 38.

| Retrieval | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| lexical | 24 | 0.9791666666666666 | 0.7999999999999999 |
| vector | 24 | 0.9583333333333334 | 0.9166666666666666 |
| hybrid | 24 | 0.9583333333333334 | 0.8958333333333334 |

| Generation | n | Schema valid | Citations valid | Status accuracy | End-to-end |
| --- | --- | --- | --- | --- | --- |
| evidencedesk-gemma-4-12b-lora | 38 | 1.0 | 0.9474 | 0.8947 | 0.8947 |

Served models: {'gemma-4-12b-it-qat-q4': 38}. Tokens: {'prompt_tokens': 48783, 'completion_tokens': 7714}.

Latency n=38: p50 21697.815000000002 ms; p95 43227.634 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `retry-recovery-1`: `invalid_citation`.
- `export-filters-2`: `invalid_citation`.
- `sandbox-cap-conflict-1`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-2`: expected answer/abstention status disagreed.
- `replay-retention-1`: retrieval miss in vector, hybrid.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty-eight scenarios are a compact regression corpus, not a market benchmark.
