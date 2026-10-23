# Live model evaluation

Human review: pending.

Commit: `54f143e42af1897a9b1e82c439e155e1cee25170`

Mode/split: live / all. Processed: 40/40 cases.
Prompt: `support-v3`. Model: `evidencedesk-gemma-4-12b-lora-0516`.
Embedding: `@cf/baai/bge-small-en-v1.5` (384 dimensions).
Dataset hash: `cd577f8a745391e1b9c16ae992f25d333f963da66cc887ea1a757a6fd8193dba`.
Corpus hash: `16e987278345dbf656f4f367a2e64e1d47a968f48a9b29b01fc3bc4109fbcce9`.
Generation attempts/completions: 30 / 30.

| Retrieval | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| lexical | 16 | 1.0 | 0.703125 |
| vector | 16 | 1.0 | 0.921875 |
| hybrid | 16 | 1.0 | 0.875 |

| Generation | n | Schema valid | Citations valid | Status accuracy | End-to-end |
| --- | --- | --- | --- | --- | --- |
| evidencedesk-gemma-4-12b-lora-0516 | 30 | 1.0 | 0.9 | 0.8333 | 0.8333 |

Served models: {'evidencedesk-gemma-4-12b-lora-0516': 30}. Tokens: {'prompt_tokens': 38609, 'completion_tokens': 3349}.

Latency n=30: p50 4952.455 ms; p95 8683.911499999998 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `webhook-signature-1`: `invalid_citation`.
- `export-filters-2`: `invalid_citation`.
- `obsolete-vs-current-2`: `invalid_citation`.
- `foreign-export-1`: expected answer/abstention status disagreed.
- `foreign-export-2`: expected answer/abstention status disagreed.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty scenarios are a compact regression corpus, not a market benchmark.
