# Security boundaries

EvidenceDesk is a personal demonstration with synthetic data. Do not enter secrets or real customer information. Report vulnerabilities privately to the repository owner through GitHub; do not disclose exploitable details in public issues.

The browser holds a random HttpOnly sandbox cookie. The BFF validates same-origin writes and forwards only explicit routes to a fixed API origin. A separate service credential and the hashed session token are checked by Python. Tenant identity is server-assigned. Ticket/run/proposal reads are session-scoped; sources are tenant-scoped, active original documents. All session responses are no-store.

Application data is in the non-exposed `evidence` schema with PUBLIC access revoked. Assign the `evidencedesk_runtime` group to a dedicated login role; never use an owner, Supabase anonymous key, or service-role Data API key as a runtime database credential. Migrations/ingestion use a separate owner connection. Keep `evidence` out of Supabase exposed schemas. This is application-level isolation, not comprehensive enterprise RBAC or a claim of database row-level security.

The model can return structured claims and optional note text only. Every cited ID must be in the authorized retrieval set and every quote must be present verbatim. This does not prove semantic correctness. Prompt injection cannot change SQL, tenant identity, or expose mutation tools. A human must inspect the exact note.

Proposals are immutable, hashed, scoped, expiring and version-bound. Approval locks the proposal and ticket and commits note insertion, version increment, status and audit together. Proposal uniqueness enforces one database effect under concurrent retries. Rejection does not mutate the ticket. No transaction spans a provider network call.

Quotas are atomic PostgreSQL counters. Analysis reserves capacity before embeddings; controlled generation retries consume another budget unit. Limits are per session and environment, not a precise shared Cloudflare neuron balance. Session creation and stored session counts are capped. Scheduled cleanup is not installed automatically; run the bounded cleanup command periodically. No keepalive traffic.

Keep credentials in ignored local environment files or encrypted project-scoped Vercel variables. Separate production and development resources. Never return database URLs, service keys, Cloudflare tokens, or provider exception payloads to a browser or log them. CI uses disposable PostgreSQL and provider doubles only.
