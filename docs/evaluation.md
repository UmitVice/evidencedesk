# Evaluation method

The fixed dataset has 40 labeled cases with 24 development and 16 holdout cases. Paraphrase groups never cross splits. The initial split-count check caught a 23/17 construction error, corrected before any quality evaluation. Do not tune using holdout outputs. No thresholds have been tuned on the holdout; the cosine cutoff is an explicit conservative starting heuristic, not a calibrated abstention guarantee.

Run offline engineering checks with `TEST_DATABASE_URL` pointed at a disposable `evidencedesk_test*` database. Tests verify actual PostgreSQL authorization, quotas, and concurrent final state. These are separate from model-quality measurements.

Create a separate `evidencedesk_eval*` database, migrate and seed it, then run:

```
uv run --project apps/api python -m evidencedesk.evaluation --mode offline --split all --limit 40
```

The offline report measures retrieval for 30 language scenarios. It does not select fixture answers using expected labels or publish offline answer-quality metrics. Ten action/provider/malformed scenarios retain explicit engineering-test references; they are not silently counted as model passes. The separate test suite exercises deterministic fixture generation and citation integrity; it is not a general question-answering model.

For live evaluation, configure Cloudflare, run `python -m evidencedesk.cli ingest-live`, then first run `python -m evidencedesk.evaluation --mode live --split development --limit 10`. Only after inspection run a larger explicit capped suite. The same durable account/environment budget is used for maintenance and evaluation calls. The default ten-attempt daily evaluation budget can require multiple days; never work around account quotas. A partial report records the point where the run stopped.

All three retrieval methods receive the same query embedding, eligible tenant, active versions, and candidate limit. PostgreSQL lexical search uses `ts_rank_cd` and OR-connected query terms, not BM25. Vector search uses exact cosine distance and a configurable cutoff; hybrid uses reciprocal rank fusion with k=60. Recall@5 uses unique document IDs and averages the fraction of labeled relevant documents found; MRR uses the first relevant document. Only executed cases with nonempty labels contribute to the denominator. The corpus currently has one short chunk per document.

Schema validity, citation membership, and exact quote containment are integrity checks. Correct abstention compares output status to the label, not semantic truth. Human review remains pending. Suggested rubric (0–2 each): correctness, completeness, support for recommendations, appropriate abstention. A human must actually inspect the answers before review status changes.

No meaningful live latency sample or usage receipt is available yet. Timing and cost are null. Reports carry Git SHA, dirty-tree flag, dataset/corpus hashes, model/manifest, prompt version, settings, timestamps, category counts and failures. Regenerate reports from a committed revision for final evidence. The UI never starts evaluations.
