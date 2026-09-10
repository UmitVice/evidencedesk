# Live model evaluation

Human review: pending.

Commit: `61a551925516100e2b075214f7e5b4336c547918`

| Retrieval | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| lexical | 6 | 1.0 | 0.8055555555555555 |
| vector | 6 | 1.0 | 0.9166666666666666 |
| hybrid | 6 | 1.0 | 1.0 |

Citation integrity does not prove semantic correctness.
Offline reports measure fixture retrieval only; generation integrity is covered by tests.
Control scenarios require separate real-database engineering tests.
Forty scenarios are a compact regression corpus, not a market benchmark.
