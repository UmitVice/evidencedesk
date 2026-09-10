# Final engineering review

This is a separate assistant self-review after live activation and the ticket-first redesign, not an independent human endorsement or an answer-quality review.

## Material findings addressed

- Live JSON-schema responses could contradict their own status and claims. The application failed closed. The support-v2 contract uses JSON-object mode, explicit shapes/schema in the prompt, and the actual ticket question when optional input is blank. Strict schema and citation validators remain unchanged. Real hosted answer and abstention checks passed; the earlier evaluation failures are preserved.
- The old workspace labeled configured live mode as “Live AI” before a successful run. The new label requires a completed live run and a recorded generation attempt. Configuration alone says “Ready for live analysis”; errors say “Unavailable”; retrieval-only abstention is labeled separately. A dedicated browser test checks the configuration-only state.
- Evidence inspection disabled its opening button while loading, so native dialog close did not reliably restore focus. The source opener is now retained and focused on close; Escape/focus return and mobile source access are tested.
- Public-schema migration metadata could inherit Supabase automatic API grants. Applied migrations 004/005 revoke metadata/schema access and default grants for the application migration role. Data API remains disabled and the runtime has no schema creation authority. Provider-managed administrator settings remain untouched.
- Live reports were conditionally loaded from a working-directory path. The evaluation page now statically imports reviewed public reports and clearly separates historical live measurements from fixture measurements and current-contract activation checks.

## Trust and transaction boundaries

Reviewed sessions, BFF forwarding, FastAPI routes, retrieval SQL, graph execution, persistence, approval transactions, migration grants, provider limits, evaluation separation, and client mutation triggers.

The browser holds an opaque HttpOnly/SameSite cookie; production cookies are Secure. The BFF checks exact Origin on writes, route allowlists, JSON content/body size, configured upstream origin, no redirects, and a bounded deadline. Service credentials remain server-only. Python independently verifies the service secret and hashed session token. Tenant identity is assigned by the server; ticket/run/proposal/source queries enforce ownership. SQL uses parameters and composite ownership foreign keys. React renders untrusted strings as text.

Provider calls run outside database transactions. Retrieval filters tenant, active versions, and compatible embedding provenance before ranking. Run-scoped source reads use stored excerpts, so document edits do not silently change evidence. Schema and exact-quote checks validate integrity, not semantic truth. The model has no SQL, shell, identity, approval, or arbitrary tool authority.

Approval locks the scoped proposal, verifies its content hash and session validity, checks final state/expiry, locks the ticket, checks expected version, inserts a unique note, increments version, and appends the audit event in one transaction. Repeated approval returns the existing note. Concurrent approve/reject and competing proposals are exercised only in isolated database tests. Production checks use disposable sessions without destructive concurrency operations.

Daily/minute counters are reserved before inference, including eligible retries. Response bytes, tokenizer inputs, candidate/context counts, graph steps, deadlines, and generation attempts remain bounded. Provider and quota errors do not switch to fixtures. Session-specific requests are no-store; no model call occurs on home-page load or session bootstrap. The UI only invokes analysis from the explicit Analyze ticket action.

## Verification and remaining limits

Local checks use native PostgreSQL 17.11/pgvector 0.8.6; CI uses its pinned real PostgreSQL container; hosted verification uses Supabase PostgreSQL 17.6/pgvector 0.8.2. The current suite has 44 Python/API/PostgreSQL tests and 13 browser tests. The full browser run passed in a separate disposable native database after repeated runs reached the existing local session-creation cap; no live quota counter was reset or bypassed. Browser coverage includes source focus return, responsive 375/768/1440 layouts, direct scenarios with zero automatic AI calls, approval/rejection, persistence, expired sessions, quota/provider errors, and no uncaught browser/hydration errors.

Release gates also include lint/types/build, generated-contract drift, npm/pip audits, ignored/tracked-secret checks, publication-tree/history scans, browser-asset scans, actual deployment SHA checks, and the live BFF/browser flow. Final run/deployment IDs accompany the release delivery record.

The support-v3 full live suite at clean `b1943513cef15e6f42335fbf2642bf094c09217c` processed all 40 cases: 30 real generation attempts/completions and ten engineering-control references. Twenty-eight outputs passed schema/citation checks, two failed structured validation, and five valid outputs disagreed with the expected answer/abstention status. Retrieval n=16: Recall@5 1.0 for all methods; MRR lexical 0.703125, vector 0.921875, hybrid 0.875. Latency n=30: p50 1.15 s, p95 2.44 s. Human semantic review remains pending. The held-out results were measured after prompt tuning and were not used to tune the released prompt.

Hosted dev is activated on its own Supabase database with restricted credentials, TLS enforcement, Data API disabled, and 24 real chunks. A diagnostic accidentally exposed the previous API preview bypass credential in tool output; it was revoked, replaced in the paired web configuration, and the web was redeployed. No production database password or Cloudflare token was displayed.

Known model limitations remain explicit: structured output can exceed the claim limit and abstention is imperfect. Invalid responses fail closed; no permissive repair or silent fixture fallback was added. Timing guidance now preserves source conditions and before/after wording. No uptime, enterprise certification, comprehensive security certification, or autonomous-agent claim is made.
