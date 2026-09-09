# Implementation status

Specification read in full on 2026-09-09. Empty designated repository inspected; existing Git identity retained. No unrelated files or remotes.

## Sequential milestones

- [x] 1. Verified stack, repository, minimal UI/API, database and CI
- [x] 2. Schema, sessions, corpus, ingestion and source reads
- [x] 3. Retrieval, providers and bounded analysis graph
- [x] 4. Immutable transactional approvals and race tests
- [x] 5. Evaluations, durable quotas and reports
- [x] 6. UI, browser tests and available free deployment
- [x] 7. Critical review, final local checks and screenshots
- [ ] Public GitHub release and remote CI (authentication blocked)
- [ ] Hosted database flow and live AI verification (credentials pending)

Validated implementation revision: `31696ba`. Final report records this clean revision. The sequential review branch is merged into dev and deleted after final evidence checks. The working checkout finishes clean on dev; master/tag/public release remain gated on remote CI.

External blockers: GitHub CLI authorization is pending. Supabase and Cloudflare browser sign-in now work. Created a project-specific EvidenceDesk Free Supabase organization and prepared evidencedesk-master (Paris, Data API and automatic table exposure disabled); the user must enter and submit the database password. Prepared a Cloudflare Workers AI Read/Edit token summary restricted to the current account; final access grant and secure token storage are pending. Vercel CLI is authenticated as umitvice. Docker is absent; native PostgreSQL 17.11/pgvector 0.8.6 provides real local verification. Compose remains the portable CI path, not a locally executed Docker claim.

Checks: frontend lint/typecheck/build, Ruff, Pyright, 1 pytest, npm audit, real PostgreSQL extension/version queries.

Milestone 2: 24 original documents, two tenants, idempotent fixture ingestion, opaque expiring sessions, bounded session creation and source ownership. The first typecheck found Psycopg typing issues; the merge was premature. Corrected immediately on the sole active branch. Ruff/Pyright now pass; all 6 tests passed against real PostgreSQL.

Milestone 3 checks: Ruff, Pyright, 13 tests passed. Real PostgreSQL retrieval and persisted fixture analysis verified. Provider REST error contracts tested with HTTPX doubles. Live smoke remains blocked by credentials; candidate model configuration is unverified live.

Milestone 4: 19 tests passed with real PostgreSQL. Eight concurrent approvals returned the same note; exactly one note and one applied audit event persisted. Rejection, stale, expired, foreign, edited proposals and pending reload verified.

Milestone 5: 23 tests passed, including atomic quotas and embedding-not-called after exhaustion. Offline report executed against an isolated evaluation database; 40 selected scenarios with 30 language evaluations and 10 explicit engineering-test references. Frontend lint/typecheck/build passed.

Milestone 6: all three pages, generated OpenAPI/TypeScript contract, secure BFF and screenshots implemented. Frontend lint/typecheck/build, 23 API/database tests and 6 browser tests passed. Two Vercel Hobby projects created; preview deployment verification pending. GitHub repository exists but push authentication is blocked.

Milestone 7: separate self-review completed (docs/release-review.md). Forty Python/API/real-PostgreSQL tests and six browser tests passed. API tests use the restricted runtime login; fresh-process recovery is verified. Frontend lint/typecheck/build, Python lint/typecheck, dependency audits, API contract and Gitleaks scans passed.

## Final local verification (2026-09-10)

- Node 24.21.0: frontend ESLint, TypeScript and optimized Next.js build passed.
- Python 3.13.14: Ruff and Pyright passed; **41 tests passed, none skipped** with TEST_DATABASE_URL and real PostgreSQL. One upstream Starlette/AnyIO deprecation warning remains.
- **6 Playwright tests passed** with fresh API/UI processes, including populated workspace and static pages at 375/768/1440 pixels. The earlier rerun was invalidated by stopping reused servers mid-test; it was rerun successfully. An initial Python command without TEST_DATABASE_URL explicitly skipped integration tests and is not counted as full verification.
- OpenAPI/TypeScript contract check, npm audit, pip-audit, tracked/history secret scan and Gitleaks 8.30.1 passed. No known dependency vulnerabilities found; pip-audit explicitly skips the editable project itself.
- No-secret frontend build and Python wheel/source build passed; unconfigured API health returns 200 and session creation returns 503. Secret files were restored without displaying their contents.
- Offline evaluation: 40 cases processed (30 retrieval-only, 10 engineering-test references), clean code revision `31696ba`. On 16 labeled retrieval cases, lexical/hybrid Recall@5 = 1.0 and MRR = 0.703125; deterministic fixture vectors have Recall@5/MRR = 0.0 at the configured cutoff. These are fixture retrieval measurements, not live answer-quality claims. Live metrics and human review remain pending.

Final API Production deployment `dpl_HYYyCMCpRYYcKfu3FgEatpuqJRmp` is READY at https://evidencedesk-api.vercel.app; public health returns 200 with explicit simulated mode. It has no hosted database yet. Web Production deployment `dpl_4ncCVQZTE2RrYqeuTrKpN4U1gUWo` is READY at https://evidencedesk-web.vercel.app. All three pages return 200; the real BFF-to-API session request returns the expected 503 `database_unavailable`, and the browser visibly shows the message. Both deployments contain the verified implementation plus regenerated offline report, before this documentation-only receipt commit. Remote CI, GitHub push/tag/release, hosted database mutation and live model quality are not claimed complete.
