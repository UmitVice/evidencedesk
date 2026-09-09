# EvidenceDesk v0.1.0

A public support-investigation reference project using original synthetic RelayNest data.

- Ticket-first home page with direct entry into webhook, credential, and export cases.
- Next.js investigation desk with claim-associated source excerpts, document version/status, exact proposed notes, explicit approval/rejection, persisted notes, and audit history.
- Python/FastAPI and bounded LangGraph workflow with lexical/vector/hybrid retrieval, real Cloudflare inference, strict structured/citation validation, and no silent fixture fallback.
- Supabase PostgreSQL/pgvector with verified TLS, restricted runtime login, five migrations, 24 real embedding chunks, immutable proposals, and concurrency-safe idempotent approvals.
- Separate historical live and fixture evaluation records, provenance, actual failures, and pending human review.
- CI and verification covering 43 PostgreSQL/API tests and 13 browser tests, lint/types/build, contract drift, dependency audits, and secret scans. Browser checks cover 375/768/1440 layouts, focus return, error states, and no AI calls on navigation.

[Production web](https://evidencedesk-web.vercel.app) · [API health](https://evidencedesk-api.vercel.app/health)

The production baseline and final release checks exercise real session creation, retrieval/generation, authorized evidence, exact-note approval/persistence, rejection, repeated approval, tampered and foreign requests, stale proposals, and unsupported-question abstention. Final deployment IDs and CI links are included in the GitHub release record.

## Honest limits

The recorded support-v1 live evaluation made ten generation attempts/completions: eight schema/citation-valid outputs, two validation failures, and two expected-abstention disagreements. Retrieval n=6 had Recall@5 1.0 for all methods; MRR was 0.806 lexical, 0.917 vector, 1.0 hybrid. Latency n=10: p50 2.13 s, p95 4.96 s. These are historical measurements, not support-v2 quality scores or human-reviewed correctness claims.

The revised support-v2 contract passed real hosted activation checks. Its full quality reevaluation remains pending under the default daily evaluation-session budget. Citation integrity does not prove that a recommendation is correct; human review remains pending.

The protected dev web/API are deployed and isolated from production, but hosted dev sessions await completion of a separate free Supabase database through the user's new-password handoff. Local fixture development remains available. No paid plan, trial, payment method, additional provider, or unrelated resource was introduced.
