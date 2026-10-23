# Mocked behavior checks; no live model called

Human review: pending.

Commit: `3fdfaef1a5d029df29d74ece59463a2447c1d07c`

Mode/split: offline / all. Processed: 48/48 cases.
Prompt: `support-v4`. Model: `fixture-v1`.
Embedding: `fixture-hash-v1` (384 dimensions).
Dataset hash: `428655b5b1c8b43670944e22bd84f830f04c27336f10c76f0d0a414c131919dc`.
Corpus hash: `314a2457d6639c7b813bf9a600cb080b524bf752f162b86bfd73ece02f60d4d3`.
Generation attempts/completions: 0 / 0.

| Retrieval | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| lexical | 24 | 0.9583333333333334 | 0.7326388888888888 |
| vector | 24 | 0.0 | 0.0 |
| hybrid | 24 | 0.9583333333333334 | 0.7326388888888888 |

## Recorded failures and disagreements

- `retry-recovery-1`: retrieval miss in vector.
- `retry-recovery-2`: retrieval miss in vector.
- `credential-rotate-1`: retrieval miss in vector.
- `credential-rotate-2`: retrieval miss in vector.
- `export-link-1`: retrieval miss in vector.
- `export-link-2`: retrieval miss in vector.
- `webhook-signature-1`: retrieval miss in vector.
- `webhook-signature-2`: retrieval miss in vector.
- `export-filters-1`: retrieval miss in vector.
- `export-filters-2`: retrieval miss in vector.
- `api-permissions-1`: retrieval miss in vector.
- `api-permissions-2`: retrieval miss in vector.
- `obsolete-retry-1`: retrieval miss in vector.
- `obsolete-retry-2`: retrieval miss in vector.
- `obsolete-vs-current-1`: retrieval miss in vector.
- `obsolete-vs-current-2`: retrieval miss in vector.
- `credential-expiry-chain-1`: retrieval miss in vector.
- `credential-expiry-chain-2`: retrieval miss in vector.
- `sandbox-cap-conflict-1`: retrieval miss in vector.
- `sandbox-cap-conflict-2`: retrieval miss in vector.
- `export-link-chain-1`: retrieval miss in vector.
- `export-link-chain-2`: retrieval miss in vector.
- `replay-retention-1`: retrieval miss in vector.
- `replay-retention-2`: retrieval miss in vector.

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty-eight scenarios are a compact regression corpus, not a market benchmark.
