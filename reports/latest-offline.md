# Mocked behavior checks; no live model called

Human review: pending.

Commit: `99df509f38c99a79c439aa05c434c20b9f3ea90e`

| Retrieval | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| lexical | 16 | 1.0 | 0.703125 |
| vector | 16 | 0.0 | 0.0 |
| hybrid | 16 | 1.0 | 0.703125 |

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty scenarios are a compact regression corpus, not a market benchmark.
