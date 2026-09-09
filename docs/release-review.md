# Separate release review

Performed after the six implementation slices, on the sole `fix/release-review` branch. This is an assistant self-review, not an independent human approval.

## Findings fixed

- Provider read timeouts did not bound an entire streaming response. HTTPX now runs inside an asyncio total deadline, with bounded response bytes and bounded overall analysis persistence. Tests cancel a slow response and reject an oversized response.
- Live ingestion refused changed live chunks. Explicit live ingestion now invalidates their old embedding space, re-embeds only changed chunks, and fails retrieval until a compatible corpus exists. A real-PostgreSQL test verifies 24 initial embeddings, zero on an identical rerun, and one after a document change.
- Source reads could show current text after a document changed. Run-scoped source reads now return the immutable retrieved snapshot and enforce run ownership.
- Offline generation selection consulted expected labels. That invalid measurement path was removed. Offline reports measure retrieval only, leaving generation integrity to tests and live quality to explicit live runs. No resulting fixture score is advertised as semantic correctness.
- Application logging now emits sanitized request-ID/status/duration records and correlates analysis traces. It does not log prompts, credentials, or provider payloads.
- Session expiry is rechecked inside the approval transaction. Database-role tests now execute API operations through the restricted runtime login, with separate migration privileges.
- A patch-pinned Python version failed on Vercel's bundled uv. The hosted build now selects supported Python 3.13; exact CI Python uses the official setup-python distribution.
- Live production ingestion has an explicit environment guard and requires the exact provider smoke receipt.

## Transaction and trust-boundary review

Approval locks the existing scoped proposal, verifies its immutable content, rechecks session validity, checks pending state/expiry, locks the ticket, checks its expected version, inserts a unique note, increments ticket version and appends the final audit record in one transaction. Repeated applied approvals return the existing note. Reject-versus-approve races produce one final outcome. Competing proposals for one ticket make the later one stale. No provider call occurs in an open database transaction.

The BFF admits fixed routes and validates same-origin writes and body sizes. Python validates the separate service credential and opaque session hash itself. Source reads use either active tenant-scoped documents or an owned run's stored excerpts. Model output cannot select tools, tenant, SQL, shell, URLs or the applied note content. All React content is rendered as text. Citation checks do not prove semantics; human review is still necessary.

## Evidence and limits

Final command outcomes are recorded in implementation.md. Real PostgreSQL tests cover concurrency, rejection, stale/expired/foreign proposals, privileged-field edits, source snapshots, forged sessions, quotas and fresh-process recovery. Browser tests cover the full fixture flow, security boundaries and three viewport sizes. Offline/live reports are distinct. npm audit, pip-audit, a tracked/history scan and Gitleaks are run before publication.

GitHub Actions cannot yet execute because GitHub CLI authentication/push is blocked. Supabase/Cloudflare sign-in is verified, but database credentials and the Workers AI token remain pending. Hosted database mutation, live provider smoke, live quality, production branch integration and public GitHub release are not verified. No reviewer endorsements, performance improvements, coverage percentages or production reliability claims are made.
