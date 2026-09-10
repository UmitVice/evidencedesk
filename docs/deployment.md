# Deployment runbook

## Existing resources

Reuse public GitHub `UmitVice/evidencedesk`, Vercel Hobby projects `evidencedesk-web` (root `apps/web`) and `evidencedesk-api` (root `apps/api`). Both have Git integration, master as Production, and Ohio `cle1` functions. Keep dev previews protected and paired only with the dev API.

Production Supabase is the user-confirmed “UmitVice's Project,” reference `xjizbcmayuojydvwykfu`, organization `vgtbutgaevguceusemkc`, East US (Ohio). Keep its existing name, organization, and region. Do not recreate, reset, move, or purchase IPv4. PostgreSQL 17.6 / pgvector 0.8.2 were verified directly.

Production: https://evidencedesk-web.vercel.app and https://evidencedesk-api.vercel.app. Development: https://evidencedesk-web-git-dev-umitvices-projects.vercel.app and https://evidencedesk-api-git-dev-umitvices-projects.vercel.app. Dev uses the isolated Free “DevEvidenceDesk” project (`vgeyikjybphzrrarcwaj`, organization `dzjfzmicvypgsxjmldlw`, Ohio), with its own restricted runtime login and all five migrations. Never point it at production.

## Credentials and database

Existing production credentials are already entered and authenticated. Do not ask for them again without an actual authentication failure. The no-echo helper preserves existing values and local development settings:

```sh
python3 scripts/enter-cloud-credentials.py
# Only for the separate, newly created development database:
python3 scripts/enter-cloud-credentials.py --database-environment development --database-only
```

Never put credential values in command arguments, chat, logs, screenshots, source archives, or browser variables. Keep local files ignored and mode 0600. Database URI encoding is required for generated passwords.

Use the production session pooler `aws-0-us-east-2.pooler.supabase.com:5432` for local maintenance and transaction pooler port 6543 for serverless runtime. Runtime login is `evidencedesk_app`, a member of migration-created `evidencedesk_runtime`. It has no superuser/create-role/create-database/RLS-bypass authority, no corpus writes, and no proposal-content updates. Deploy only its runtime connection, never the administrator connection.

The connector enforces `sslmode=verify-full` for Supabase hosts using the bundled official public CA. Prepared statements are disabled. TLS enforcement is enabled, Data API is disabled, and the application uses private schema `evidence`. Migrations 004/005 remove application metadata exposure and automatic API grants for new migration-owner objects. Provider-managed administrator defaults are not modified.

Run only pending checksum-verified migrations from trusted local maintenance configuration. Never migrate or seed during imports, startup, or web requests. Do not alter an applied migration, truncate production, or run integration tests against it.

Production live ingestion requires a real provider receipt and explicit authorization flag:

```sh
uv run --project apps/api python -m evidencedesk.cli ingest-live --allow-production --smoke-receipt reports/provider-smoke.json
```

All 24 production chunks have verified BGE cls embeddings. Repeat ingestion changes zero unchanged chunks. Model, dimension, pooling, preprocessing, corpus version, document version, and content hashes prevent fixture/live mixing.

## Environment scopes

API server-only: DATABASE_URL, SERVICE_KEY, ENVIRONMENT, AI_MODE, AI_ENABLED, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN. Production uses `production` / `live`; dev uses `development` / `live` with branch-specific Preview values. Missing configuration remains a clear error, not a fallback. Administrative MIGRATION_DATABASE_URL is never deployed.

Web server-only: API_ORIGIN, matching SERVICE_KEY, APP_ORIGIN. Production origins use the public aliases above. The dev branch uses its exact stable web alias for Origin checks. Task previews use their own VERCEL_URL. Protected preview API requests also use the existing VERCEL_AUTOMATION_BYPASS_SECRET, server-only. Never disable deployment protection globally or introduce NEXT_PUBLIC secrets.

After changing scoped values, redeploy. A previous READY result does not prove new environment settings are active. Verify actual Git SHA, aliases, function region, BFF session creation, real retrieval/generation, citations, note decisions, and persistence. Keep production and preview service credentials distinct.

The Python deployment includes tokenizer and public CA assets; excludes private configuration, virtual environments, test corpora, and migration tooling. The web build needs only reviewed public report data, not cloud credentials. Both apps build without production secrets.

## Workers AI and quotas

Use the existing free Cloudflare account and scoped Workers AI Read/Edit token. No Worker, paid AI Gateway, second provider, local LLM, or GPU is required. Models: `@cf/baai/bge-small-en-v1.5` (384 dimensions, cls, actual tokenizer cap 512) and `@cf/meta/llama-3.1-8b-instruct-fast`.

The support-v3 generation contract uses JSON-object mode and the schema in the system prompt. Always retain strict Pydantic validation, exact quote/source authorization, immutable proposals, bounded deadlines, and no live-to-fixture fallback. Real request failures remain visible.

The account's shared free allowance is 10,000 Neurons/day. Application limits are two analyses/minute, ten daily attempts/session, forty/environment by default. Maintenance and retries reserve budget before calls. Stop on quota errors; do not reset counters or change identities to extend live evaluation. AI_ENABLED=false is the kill switch. Cleanup is a bounded explicit maintenance command, not keepalive traffic.

## Development and release

The user created the separate Ohio project named “DevEvidenceDesk” and completed the development-only credential helper. Authentication, five migrations, restricted transaction-pooler access, and 24 real BGE chunks are verified. A repeated ingestion changes zero chunks. Data API is disabled and TLS enforcement is enabled. API secrets are scoped to the dev branch; other task previews do not receive dev database access. Never reuse the production password/DSN in Preview.

For each task: inspect Git state and reconcile divergence safely. When master/dev are synchronized, create one work branch from master. Use incremental English Conventional Commits and scan staged content before each commit and publication. Merge/push to dev, verify CI and the paired dev deployments, then fast-forward master and verify production. Keep the work branch locally and remotely. Never force push, discard unrelated work, move existing tags, or delete deployment history.

The bounded hosted browser check in `playwright.hosted.config.ts` uses exactly two explicit live analyses per run, with no retries. Set `HOSTED_URL` to the existing dev or production web origin and run `npx playwright test --config playwright.hosted.config.ts`. For protected dev, `HOSTED_AUTH_FILE` may point to an ignored mode-0600 JSON file with `origin` and existing automation `headers`; the test scopes headers to that exact origin, never page JavaScript or URLs. Traces/videos are disabled to avoid recording access credentials. Check existing daily capacity first; never change quota counters or deployment protection. This is functional verification, not a new model-quality evaluation.
