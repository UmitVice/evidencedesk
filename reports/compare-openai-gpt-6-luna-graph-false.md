# Live model evaluation

Human review: only answers with review flags or failed fact checks.

Commit: `45df8765945ec4abe7479b167a15e2d1e5286aa6`

Mode/split: live / all. Processed: 48/48 cases.
Prompt: `support-v5`. Model: `gpt-6-luna`.
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
| gpt-6-luna | 38 | 1.0 | 1.0 | 0.8158 | 0.8158 |

Served models: {'gpt-6-luna': 38}. Tokens: {'prompt_tokens': 56219, 'completion_tokens': 8769}.

Automatic fact checks: 0.8158 pass (status right, labeled facts present, no obsolete fact asserted). Review flags raised on 0 answers, 0 of them failing the fact check.

Latency n=38: p50 3139.2349999999997 ms; p95 6174.2515 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `obsolete-vs-current-1`: expected answer/abstention status disagreed.
- `obsolete-vs-current-2`: expected answer/abstention status disagreed.
- `injection-source-1`: expected answer/abstention status disagreed.
- `injection-source-2`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-1`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-2`: expected answer/abstention status disagreed.
- `replay-retention-1`: expected answer/abstention status disagreed.
- `replay-retention-1`: retrieval miss in vector.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty-eight scenarios are a compact regression corpus, not a market benchmark.
