# Implementation status

## Current state

EvidenceDesk is implemented as a three-route ticket investigation desk. The production baseline at `0031c480f764498c23b1d9f72c919efe11311c4e` was verified through the deployed browser and public BFF before redesign. The redesigned UI has direct scenario entry, claim-associated evidence inspection, exact-note approval, separate saved notes/audit events, and recorded live/fixture evaluation sections. Final deployment identifiers and release checks are recorded in the GitHub release and delivery report.

- **GitHub:** existing public [UmitVice/evidencedesk](https://github.com/UmitVice/evidencedesk) reused; CLI identity UmitVice verified; master is the default/production branch. Permanent branches are dev and master; one temporary branch at a time.
- **Production:** [web](https://evidencedesk-web.vercel.app) and [API health](https://evidencedesk-api.vercel.app/health). Both Vercel projects use Ohio `cle1`, GitHub integration, and paired server-only credentials. Public web → BFF → API → Supabase → real Workers AI → source validation → explicit decision → persisted note was verified.
- **Database:** confirmed production project `xjizbcmayuojydvwykfu`, generic name “UmitVice's Project” retained, organization `vgtbutgaevguceusemkc`, East US (Ohio). Actual PostgreSQL 17.6 and pgvector 0.8.2. Five checksum-verified migrations applied without resets. Data API disabled; TLS enforcement enabled; automatic API grants removed for new objects owned by the migration role. Provider-managed `supabase_admin` defaults are untouched.
- **Runtime:** dedicated `evidencedesk_app` login through transaction pooler 6543, prepared statements disabled, hostname/certificate verification enforced with the official Supabase CA. No schema/role/database creation, RLS bypass, corpus writes, or proposal-content updates. Migration/admin connection remains local and ignored.
- **Corpus:** 24 real BGE chunks; model/pooling/preprocessing/version manifest verified. Identical ingestion changes zero. Known webhook vector and hybrid retrieval return the retry document first. Fixture and real embedding spaces stay separate.
- **Workers AI:** existing scoped token works. Embedding `@cf/baai/bge-small-en-v1.5`, generation `@cf/meta/llama-3.1-8b-instruct-fast`. `support-v2` uses JSON-object mode plus an explicit schema/prompt and strict local schema/citation validation. No live-to-fixture fallback.
- **Development:** [web preview](https://evidencedesk-web-git-dev-umitvices-projects.vercel.app) pairs only with [dev API](https://evidencedesk-api-git-dev-umitvices-projects.vercel.app). Preview protection is retained. The separate Free project “DevEvidenceDesk” (`vgeyikjybphzrrarcwaj`, organization `dzjfzmicvypgsxjmldlw`, Ohio) is configured with PostgreSQL 17.6, pgvector 0.8.2, all five migrations, a distinct restricted runtime credential, and 24 real BGE chunks; dev never uses production credentials/state. Local native PostgreSQL 17.11 / pgvector 0.8.6 remains available.
- **Dev credential handoff resolved:** the user-created database and securely entered password authenticated successfully. Its own runtime connection and Cloudflare settings are scoped to the dev branch only. Data API is disabled and TLS enforcement is enabled. No paid capacity or production credential sharing was needed.

## Verified evidence and limits

Baseline master CI: [34416525370](https://github.com/UmitVice/evidencedesk/actions/runs/34416525370); baseline dev CI: [34416333589](https://github.com/UmitVice/evidencedesk/actions/runs/34416333589). Both ran 43 Python/API/PostgreSQL tests and six pre-redesign browser tests. The redesign expands browser coverage to 13 tests. Native database tests and GitHub's PostgreSQL container are distinct; local Docker was not used.

The production baseline BFF checks passed session/ticket creation, real generation, exact authorized quotations, approval of the exact note, repeated approval with one note, rejection without a note, foreign session/run/proposal rejection, tampered content rejection, stale proposals, and unsupported-question abstention. Browser checks independently confirmed live source inspection, approval, refresh persistence, and rejection. Baseline deployments: API `dpl_5413aMmkq1X3BAHZS7yPx8oQq2yT`, web `dpl_HADXaR6cs3HdnYPShg1eTnSYG9t6`.

The historical live evaluation at clean `603062b` / support-v1 made ten generation attempts and completed ten provider responses: eight passed schema/citation checks, two SSO cases failed validation, and two obsolete-policy cases disagreed with expected abstention. Retrieval n=6: Recall@5 1.0 for all methods; MRR lexical 0.806, vector 0.917, hybrid 1.0. Latency n=10, p50 2.13 s, p95 4.96 s. Human review remains pending. These are not support-v2 quality scores. The daily evaluation-session budget was reached; it was not reset or bypassed. The current contract passed separate hosted activation checks, but its complete quality reevaluation remains pending.

The original structured provider contract failed closed during activation. A bounded diagnostic reproduced contradictory insufficient-evidence claims. The revised contract preserves all validators and uses the actual ticket question when optional input is empty. Earlier failed measurements remain in the repository.

Secret files remain ignored/untracked and server-only. Only the reviewed `.env.example` is tracked. Source deployment exclusions cover private configuration and caches. Release gates include lint/types/build, actual PostgreSQL tests, browser checks, API-contract drift, dependency audits, staged publication/history scans, and deployed functional checks.

## History

[Superseded snapshots](history/implementation-snapshots.md) preserve milestone evidence, original blockers, and corrections. They are not current setup instructions.
