# Live model evaluation

Human review: pending.

Commit: `96aac272370569aa0421d67c9167a078b8a16836`

Mode/split: live / all. Processed: 48/48 cases.
Prompt: `support-v5`. Model: `evidencedesk-gemma-4-12b-Q4_0`.
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
| evidencedesk-gemma-4-12b-Q4_0 | 38 | 1.0 | 0.9737 | 0.8684 | 0.8684 |

Served models: {'evidencedesk-gemma-4-12b-Q4_0': 38}. Tokens: {'prompt_tokens': 51781, 'completion_tokens': 3131}.

Latency n=38: p50 4491.1 ms; p95 6021.3705 ms. Live embedding, three retrieval methods, and optional generation; includes failures.

## Recorded failures and disagreements

- `export-filters-2`: `invalid_citation`.
- `obsolete-vs-current-1`: expected answer/abstention status disagreed.
- `obsolete-vs-current-2`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-1`: expected answer/abstention status disagreed.
- `sandbox-cap-conflict-2`: expected answer/abstention status disagreed.
- `replay-retention-1`: retrieval miss in vector.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty-eight scenarios are a compact regression corpus, not a market benchmark.
