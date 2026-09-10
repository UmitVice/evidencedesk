# EvidenceDesk v0.1.1

- Activate the isolated Free development database and paired Vercel preview, including five migrations, restricted runtime credentials, TLS enforcement, and 24 real embedding chunks.
- Preserve source timing conditions and policy status in support-v3 guidance. The export recovery regression now distinguishes link expiry from seven-day export retention.
- Publish the full live evaluation with preserved smoke/history, explicit budgets, and sanitized validation diagnostics.
- Rotate the API preview bypass credential after a diagnostic exposure and redeploy the paired web.
- Verify 44 PostgreSQL/API tests and 13 browser tests, builds/types/lint, audits, secret scans, and hosted workflows.

## Measured limits

The support-v3 full live suite at clean `b1943513cef15e6f42335fbf2642bf094c09217c` processed all 40 cases: 30 real generation attempts/completions and ten engineering-control references. Twenty-eight outputs passed schema/citation checks, two failed structured validation, and five valid outputs disagreed with the expected answer/abstention status. Retrieval n=16: Recall@5 1.0 for all methods; MRR lexical 0.703125, vector 0.921875, hybrid 0.875. Latency n=30: p50 1.15 s, p95 2.44 s. Human semantic review remains pending. The held-out results were measured after prompt tuning and were not used to tune the released prompt.

Invalid answers fail closed without proposals. Five answer-status disagreements remain visible; citation validation does not prove semantic truth. All production and dev resource setup is complete. No paid plan, trial, public quota increase, or counter reset was used. Final CI and deployment identifiers accompany the GitHub release. The original v0.1.0 tag remains unchanged.
