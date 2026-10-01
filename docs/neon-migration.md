# Neon Free migration

## Plan and boundaries

Move only EvidenceDesk's development and production PostgreSQL databases from
Supabase to separate Neon Free projects owned by the personal account
`umitvice@gmail.com`. The existing Vercel Hobby web/API projects remain in
`umitvices-projects`. The Vercel-managed Neon installation is Launch at the
installation level, so it must not receive the new databases or have its plan
changed. Use the separately created, console-managed EvidenceDesk Free
organization instead.

1. Verify Git synchronization, account ownership, organization plan, and region.
2. Export every application table from each source with a consistent snapshot;
   preserve corpus vectors, sessions, immutable proposals, notes, and quota counters.
   Keep ignored, restricted local backups and the old source databases for rollback.
3. Apply unchanged checksum-verified migrations to each fresh Neon project,
   restore data, compare table counts and content hashes, and create separate
   least-privilege runtime logins. Administrative credentials stay local.
4. Enforce certificate and hostname validation using certifi's Mozilla CA bundle for Neon.
   Keep bounded connection/statement/lock timeouts and disabled prepared statements.
5. Complete lint, types, unit and actual PostgreSQL tests, build, browser checks,
   API-contract checks, dependency audits, and staged/history secret scans.
6. Release the work branch to dev, update only the dev API database variable,
   and verify CI plus deployed analysis, source inspection, approval persistence,
   rejection, tenant/session isolation, and responsive accessibility.
7. Promote to master, update only the production API database variable, and
   verify both deployment revisions and the same live journey. Preserve the work
   branch locally/remotely. Do not delete source resources during this release.

No paid resources, billing changes, keepalive traffic, quota resets, model-quality
claims, or unrelated-resource changes are authorized by this migration. Neon
Free sleeps while idle and wakes on connection; it remains subject to provider
quotas and is not an always-on availability guarantee.

## Provisioned resources

- Account: `umitvice@gmail.com` (verified in Vercel and Neon).
- Organization: `EvidenceDesk`, `org-divine-wind-27513562`, plan `free`, managed by console.
- Development: `evidencedesk-dev`, `cold-mode-47834829`, PostgreSQL 17, AWS Ohio.
- Production: `evidencedesk-production`, `flat-frost-26354813`, PostgreSQL 17, AWS Ohio.
- Existing Vaniras organization: `org-summer-lab-41383333`; its Launch plan is unchanged.

## Data verification

All five unchanged migration checksums match. Each of the nine application
tables was copied from a consistent source snapshot and compared byte-for-byte
using a SHA-256 digest of deterministically ordered CSV (generated search
columns are recreated by the unchanged schema).

| Table | Development | Production |
| --- | ---: | ---: |
| sessions | 8 | 14 |
| documents | 24 | 24 |
| chunks | 24 | 24 |
| tickets | 24 | 42 |
| usage_counters | 25 | 40 |
| runs | 17 | 24 |
| proposals | 14 | 19 |
| notes | 5 | 7 |
| audit_events | 25 | 34 |

These are migration snapshot counts, before release verification creates new
sandbox sessions and runs. Quota counters were preserved without resets. Both
runtime roles passed checks for no superuser/create database/create role/RLS
bypass, no public schema creation, no corpus insertion, and no proposal content
update. Both computes are fixed at 0.25 CU with the Free plan's idle suspension.

The source runtime membership was removed before each snapshot to fence writes.
Source databases and ignored mode-0600 backups remain intact. Rollback requires
restoring `GRANT evidencedesk_runtime TO evidencedesk_app` on the corresponding
source and restoring its original Vercel database variable, followed by a
redeployment. After destination writes begin, reconcile those writes before
rolling back; the old snapshot alone is no longer a complete current database.

## Release checks

Local checks passed: lint, typecheck, build, 55 Python/API tests with native
PostgreSQL, 22 simulated browser tests, API-contract consistency, JavaScript and
Python dependency audits, and tracked/history secret scans. Required security
updates were Next.js/eslint-config-next 16.3.8, patched brace-expansion packages,
and urllib3 2.8.0. These checks do not measure live model quality.

The first deployed dev API verification passed real generation/citations,
foreign-session rejection, tampered-content rejection, idempotent exact-note
approval, stale-proposal rejection, rejection without a note, and unsupported
question abstention at commit `c2763af`. Initial hosted-browser attempts exposed
stale heading assertions (no model calls) and protected upstream access before
analysis. The headings were aligned with the existing UI. The BFF now uses the
explicit server-only `API_PROTECTION_BYPASS_SECRET` for the API preview instead
of the platform's web-project `VERCEL_AUTOMATION_BYPASS_SECRET`. Only the dev
branch gets the existing API access secret; preview protection remains enabled.

Final dev browser and production verification are pending.
