# Live model evaluation

Human review: pending.

Commit: `5fef4482a2684304c7100f2e16774fc256cc6f59`

Mode/split: live / all. Processed: 48/48 cases.
Prompt: `support-v5`. Model: `@cf/meta/llama-3.1-8b-instruct-fast`.
Embedding: `@cf/baai/bge-small-en-v1.5` (384 dimensions).
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
| @cf/meta/llama-3.1-8b-instruct-fast | 38 | 0.9737 | 0.9211 | 0.7632 | 0.7632 |

Served models: {'@cf/meta/llama-3.1-8b-instruct-fast': 38}. Tokens: {'prompt_tokens': 52552, 'completion_tokens': 6615}.

Latency n=38: p50 1620.885 ms; p95 3913.178 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `retry-recovery-1`: `invalid_citation`.
- `unknown-region-1`: expected answer/abstention status disagreed.
- `foreign-routing-2`: `invalid_model_output`.
- `foreign-export-1`: `invalid_citation`.
- `foreign-export-2`: expected answer/abstention status disagreed.
- `injection-source-1`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-1`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-2`: expected answer/abstention status disagreed.
- `replay-retention-1`: expected answer/abstention status disagreed.
- `replay-retention-1`: retrieval miss in vector, hybrid.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty-eight scenarios are a compact regression corpus, not a market benchmark.
