# Live model evaluation

Human review: pending.

Commit: `b1943513cef15e6f42335fbf2642bf094c09217c`

Mode/split: live / all. Processed: 40/40 cases.
Prompt: `support-v3`. Model: `@cf/meta/llama-3.1-8b-instruct-fast`.
Embedding: `@cf/baai/bge-small-en-v1.5` (384 dimensions).
Dataset hash: `cd577f8a745391e1b9c16ae992f25d333f963da66cc887ea1a757a6fd8193dba`.
Corpus hash: `16e987278345dbf656f4f367a2e64e1d47a968f48a9b29b01fc3bc4109fbcce9`.
Generation attempts/completions: 30 / 30.

| Retrieval | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| lexical | 16 | 1.0 | 0.703125 |
| vector | 16 | 1.0 | 0.921875 |
| hybrid | 16 | 1.0 | 0.875 |

Latency n=30: p50 1152.515 ms; p95 2436.2015 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `credential-rotate-1`: `invalid_model_output`.
- `unknown-region-1`: expected answer/abstention status disagreed.
- `obsolete-vs-current-1`: expected answer/abstention status disagreed.
- `obsolete-vs-current-2`: `invalid_model_output`.
- `foreign-routing-2`: expected answer/abstention status disagreed.
- `foreign-export-1`: expected answer/abstention status disagreed.
- `foreign-export-2`: expected answer/abstention status disagreed.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty scenarios are a compact regression corpus, not a market benchmark.
