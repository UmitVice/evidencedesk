# Implementation status

Specification read in full on 2026-09-09. Empty designated repository inspected; existing Git identity retained. No unrelated files or remotes.

## Sequential milestones

- [x] 1. Verified stack, repository, minimal UI/API, database and CI
- [x] 2. Schema, sessions, corpus, ingestion and source reads
- [x] 3. Retrieval, providers and bounded analysis graph
- [x] 4. Immutable transactional approvals and race tests
- [x] 5. Evaluations, durable quotas and reports
- [x] 6. UI, browser tests and available free deployment
- [ ] 7. Critical review, final checks, screenshots and validated release

Current branch: feat/workspace-release. Last verified commit: 2455de7; current slice checks passed before commit.

External blockers: GitHub CLI authorization requested; Supabase and Cloudflare browser sessions require sign-in. Vercel CLI is authenticated as umitvice. No cloud secrets were found in the task environment. Docker is absent; installing native PostgreSQL/pgvector for equivalent real-database local verification. Compose remains the documented portable path.

Checks: frontend lint/typecheck/build, Ruff, Pyright, 1 pytest, npm audit, real PostgreSQL extension/version queries.

Milestone 2: 24 original documents, two tenants, idempotent fixture ingestion, opaque expiring sessions, bounded session creation and source ownership. The first typecheck found Psycopg typing issues; the merge was premature. Corrected immediately on the sole active branch. Ruff/Pyright now pass; all 6 tests passed against real PostgreSQL.

Milestone 3 checks: Ruff, Pyright, 13 tests passed. Real PostgreSQL retrieval and persisted fixture analysis verified. Provider REST error contracts tested with HTTPX doubles. Live smoke remains blocked by credentials; candidate model configuration is unverified live.

Milestone 4: 19 tests passed with real PostgreSQL. Eight concurrent approvals returned the same note; exactly one note and one applied audit event persisted. Rejection, stale, expired, foreign, edited proposals and pending reload verified.

Milestone 5: 23 tests passed, including atomic quotas and embedding-not-called after exhaustion. Offline report executed against an isolated evaluation database; 40 selected scenarios with 30 language evaluations and 10 explicit engineering-test references. Frontend lint/typecheck/build passed.

Milestone 6: all three pages, generated OpenAPI/TypeScript contract, secure BFF and screenshots implemented. Frontend lint/typecheck/build, 23 API/database tests and 6 browser tests passed. Two Vercel Hobby projects created; preview deployment verification pending. GitHub repository exists but push authentication is blocked.

Next: separate critical review, final evidence, available deployment, release gates. Remote CI remains unverified until GitHub authorization.
