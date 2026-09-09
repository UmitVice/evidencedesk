# Implementation status

## Current state — live activation in progress

The user confirmed the existing Ohio project as production and supplied credentials through the no-echo helper. Earlier blockers below are superseded.

- GitHub: authenticated UmitVice; existing repository reused. dev 8c0179e passed remote CI with 42 API/PostgreSQL tests and 6 browser tests: https://github.com/UmitVice/evidencedesk/actions/runs/34412031768.
- Production database: xjizbcmayuojydvwykfu in organization vgtbutgaevguceusemkc, generic name preserved, East US (Ohio). Actual PostgreSQL 17.6 and pgvector 0.8.2 verified. Four migrations applied without resets. Data API disabled and TLS enforcement enabled.
- Runtime: separate evidencedesk_app login verified through transaction pooler port 6543 with full hostname/certificate verification. It cannot create schemas/roles/databases, bypass RLS, or update proposal content. Administrative credentials remain only in ignored local maintenance configuration. Anonymous schema access is denied.
- Corpus: 24 real BGE embeddings ingested; identical repeat changes zero. Known webhook query finds webhook-retries first in real vector and hybrid search. Fixture and real manifests remain distinct.
- Workers AI: stored token verified active. Real embedding and structured generation smoke passed at code revision 8c0179e; see reports/provider-smoke.json. Human review is pending.
- Vercel: existing API and web projects connected to GitHub/master Production. Production API runtime credentials configured; new deployment and hosted functional verification pending. Function region is being aligned to Ohio (cle1).
- Development: local PostgreSQL remains isolated. Separate free evidencedesk-dev form prepared in the empty EvidenceDesk organization, Ohio, Data API/automatic exposure off. Creating this new database requires user submission of its new password; production credentials already work and require no re-entry.
- Remaining work: baseline hosted verification, ten-case live evaluation, redesigned ticket-first UI, final CI/dev/production deployment and release. Do not claim current hosted live functionality until tested.

The live ten-case evaluation at clean revision `603062b` completed ten generation calls: six expected answers, two SSO schema-validation failures, and two obsolete-policy expectation failures. All six labeled answerable cases had Recall@5 1.0 for each method; hybrid MRR was 1.0. Human review is pending. The default ten-attempt evaluation-session budget is exhausted for today; no counters were reset or identities changed to extend it. Migration 005 also removes automatic public-schema API grants for newly created objects.

## Historical notes — superseded snapshots


Specification read in full on 2026-09-09. Empty designated repository inspected; existing Git identity retained. No unrelated files or remotes.

## Resumed resource verification (2026-09-10)

This section supersedes the earlier authentication snapshot.

| Resource | Created | Configured | Verified | Blocked |
| --- | --- | --- | --- | --- |
| GitHub | Existing public UmitVice/evidencedesk reused | HTTPS CLI identity UmitVice; master default; master/dev pushed | dev 7f01e15 passed Linux CI: 41 PostgreSQL/API tests, 6 browser tests, build/audits/scans | Final live release gates pending |
| Vercel API | Existing prj_OgnoPz5PFagUg0wwa8dczuQ6xvMN reused | apps/api, FastAPI, master Production; GitHub link connected; distinct service secrets | Production dpl_HYYyCMCpRYYcKfu3FgEatpuqJRmp, code 31696ba; preview protection retained | Runtime database and AI token missing |
| Vercel web | Existing prj_MPCvHinnOH8yUVwbf1HWgmynslpp reused | apps/web, Next.js, Node 24.x, master Production; GitHub link connected | Production dpl_4ncCVQZTE2RrYqeuTrKpN4U1gUWo, code 31696ba; production API origin paired | Hosted session/live flow awaits API credentials |
| Supabase | EvidenceDesk Free organization dzjfzmicvypgsxjmldlw verified | No EvidenceDesk database created during resume | Organization remains empty; another Free organization has one Healthy Ohio project | User must confirm whether that existing project is intended for EvidenceDesk; no mutations made to it |
| Cloudflare | Existing Active Workers AI token reused; no duplicate token | Dashboard verifies Workers AI Read/Edit for the intended account only | Token existence and scope verified; current model documentation inspected | Token value absent locally; no live requests made |
| Local configuration | Existing root .env and web .env.local preserved | Secret files mode 600, private directory mode 700; secure interactive helper added | Only .env.example tracked; history and staged publication scan clean | Database password and AI token need no-echo terminal entry |

Initial remote CI: https://github.com/UmitVice/evidencedesk/actions/runs/34411297938. Linux CI actually ran its pinned PostgreSQL/pgvector container; local database testing remains native PostgreSQL, not local Docker.

The full worktree scan flagged generated local application secrets and Next.js caches (plus a Node header false positive). All findings are untracked and ignored. The separately exported publication tree and reachable Git history passed Gitleaks; no secret finding was bypassed or pushed. Added Docker-context exclusions; existing deployment and package exclusions remain in force.

`codex/live-release` adds secure credential entry and explicit generation-attempt/completion counts plus measured live-case latency. A regression test confirms that local abstention does not count as a model generation. All 42 Python/API/PostgreSQL tests pass locally with no integration skips. No live metric is populated from this mocked regression test.

Credential entry command: `python3 scripts/enter-cloud-credentials.py` from a real terminal. It accepts the saved database password and Workers AI token without echo, rejects noninteractive/echo-fallback input, and writes only ignored mode-600 files. Password URI encoding and production runtime-role provisioning occur only after project identity and connection metadata are verified. Root local-development DSNs and the BFF service credential are preserved.

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
