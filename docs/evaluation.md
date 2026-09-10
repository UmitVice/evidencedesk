# Evaluation method

The fixed dataset has 40 labeled cases with 24 development and 16 holdout cases. Paraphrase groups never cross splits. The initial split-count check caught a 23/17 construction error, corrected before any quality evaluation. Do not tune using holdout outputs. No thresholds have been tuned on the holdout; the cosine cutoff is an explicit conservative starting heuristic, not a calibrated abstention guarantee.

Run offline engineering checks with `TEST_DATABASE_URL` pointed at a disposable `evidencedesk_test*` database. Tests verify actual PostgreSQL authorization, quotas, and concurrent final state. These are separate from model-quality measurements.

Create a separate `evidencedesk_eval*` database, migrate and seed it, then run:

```
uv run --project apps/api python -m evidencedesk.evaluation --mode offline --split all --limit 40
```

The offline report measures retrieval for 30 language scenarios. It does not select fixture answers using expected labels or publish offline answer-quality metrics. Ten action/provider/malformed scenarios retain explicit engineering-test references; they are not silently counted as model passes. The separate test suite exercises deterministic fixture generation and citation integrity; it is not a general question-answering model.

For live evaluation, configure Cloudflare, run `python -m evidencedesk.cli ingest-live`, then first run `python -m evidencedesk.evaluation --mode live --split development --limit 10`. Only after inspection run a larger explicit capped suite. The same durable environment and evaluation-session counters cover smoke and full runs. After checking free account headroom, an explicitly bounded maintainer process may use `ATTEMPTS_PER_SESSION_DAY=40 uv run --project apps/api python -m evidencedesk.evaluation --mode live --split all --limit 40`. This does not change deployed sandbox settings or the default 40-attempt environment cap. Existing attempts count toward that cap; never reset counters or change identity to avoid it. A partial report records a quota stop.

All three retrieval methods receive the same query embedding, eligible tenant, active versions, and candidate limit. PostgreSQL lexical search uses `ts_rank_cd` and OR-connected query terms, not BM25. Vector search uses exact cosine distance and a configurable cutoff; hybrid uses reciprocal rank fusion with k=60. Recall@5 uses unique document IDs and averages the fraction of labeled relevant documents found; MRR uses the first relevant document. Only executed cases with nonempty labels contribute to the denominator. The corpus currently has one short chunk per document.

Schema validity, citation membership, and exact quote containment are integrity checks. Correct abstention compares output status to the label, not semantic truth. Human review remains pending. Suggested rubric (0–2 each): correctness, completeness, support for recommendations, appropriate abstention. A human must actually inspect the answers before review status changes.

The support-v3 full live suite at clean `b1943513cef15e6f42335fbf2642bf094c09217c` processed all 40 cases: 30 real generation attempts/completions and ten engineering-control references. Twenty-eight outputs passed schema/citation checks, two failed structured validation, and five valid outputs disagreed with the expected answer/abstention status. Retrieval n=16: Recall@5 1.0 for all methods; MRR lexical 0.703125, vector 0.921875, hybrid 0.875. Latency n=30: p50 1.15 s, p95 2.44 s. Human semantic review remains pending. The held-out results were measured after prompt tuning and were not used to tune the released prompt.

The full run followed a ten-case smoke (nine valid outputs, one structured failure). Cloudflare showed 126.58/10,000 free Neurons used before the full run. The process-only evaluation session budget was explicitly set to 40; ten smoke reservations plus thirty full-suite reservations reached the unchanged 40-attempt environment budget. Previous counters and failed cases remain intact. No public sandbox budget or account plan changed.

Reports record exact revisions, dirty-tree flag, dataset/corpus hashes, models, prompt, budgets, counts, failures and timings. Validation diagnostics contain field paths and error types only, never raw invalid model input. Historical support-v1 results and support-v3 smoke are preserved in `reports/history`. Exact monetary cost and human quality scores remain unreported. The UI never starts evaluations.
