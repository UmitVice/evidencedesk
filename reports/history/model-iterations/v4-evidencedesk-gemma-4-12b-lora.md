# Live model evaluation

Human review: pending.

Commit: `8bd2c29d28a99fe822d090437e5b313acfad0cd5`

Mode/split: live / all. Processed: 40/40 cases.
Prompt: `support-v4`. Model: `evidencedesk-gemma-4-12b-lora`.
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
| evidencedesk-gemma-4-12b-lora | 30 | 1.0 | 1.0 | 0.7333 | 0.7333 |

Served models: {'evidencedesk-gemma-4-12b-lora': 30}. Tokens: {'prompt_tokens': 38609, 'completion_tokens': 1672}.

Latency n=30: p50 4224.139999999999 ms; p95 10005.2895 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `retry-recovery-2`: expected answer/abstention status disagreed.
- `credential-rotate-1`: expected answer/abstention status disagreed.
- `export-link-1`: expected answer/abstention status disagreed.
- `export-link-2`: expected answer/abstention status disagreed.
- `obsolete-retry-1`: expected answer/abstention status disagreed.
- `obsolete-retry-2`: expected answer/abstention status disagreed.
- `obsolete-vs-current-1`: expected answer/abstention status disagreed.
- `obsolete-vs-current-2`: expected answer/abstention status disagreed.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty scenarios are a compact regression corpus, not a market benchmark.
