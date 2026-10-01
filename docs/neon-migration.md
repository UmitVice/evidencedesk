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

Migration and release verification are pending. Provisioning alone does not
establish data parity or a working application.
