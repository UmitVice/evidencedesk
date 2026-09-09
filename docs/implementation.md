# Implementation status

Specification read in full on 2026-09-09. Empty designated repository inspected; existing Git identity retained. No unrelated files or remotes.

## Sequential milestones

- [x] 1. Verified stack, repository, minimal UI/API, database and CI
- [x] 2. Schema, sessions, corpus, ingestion and source reads
- [x] 3. Retrieval, providers and bounded analysis graph
- [x] 4. Immutable transactional approvals and race tests
- [ ] 5. Evaluations, durable quotas and reports
- [ ] 6. UI, browser tests and available free deployment
- [ ] 7. Critical review, final checks, screenshots and validated release

Current branch: feat/approved-actions. Last verified commit: 9990078; current slice checks passed before commit.

External blockers: GitHub CLI authorization requested; Supabase and Cloudflare browser sessions require sign-in. Vercel CLI is authenticated as umitvice. No cloud secrets were found in the task environment. Docker is absent; installing native PostgreSQL/pgvector for equivalent real-database local verification. Compose remains the documented portable path.

Checks: frontend lint/typecheck/build, Ruff, Pyright, 1 pytest, npm audit, real PostgreSQL extension/version queries.

Milestone 2: 24 original documents, two tenants, idempotent fixture ingestion, opaque expiring sessions, bounded session creation and source ownership. The first typecheck found Psycopg typing issues; the merge was premature. Corrected immediately on the sole active branch. Ruff/Pyright now pass; all 6 tests passed against real PostgreSQL.

Milestone 3 checks: Ruff, Pyright, 13 tests passed. Real PostgreSQL retrieval and persisted fixture analysis verified. Provider REST error contracts tested with HTTPX doubles. Live smoke remains blocked by credentials; candidate model configuration is unverified live.

Milestone 4: 19 tests passed with real PostgreSQL. Eight concurrent approvals returned the same note; exactly one note and one applied audit event persisted. Rejection, stale, expired, foreign, edited proposals and pending reload verified.

Next: fixed evaluation dataset and reports. Remote CI remains unverified until GitHub authorization.
