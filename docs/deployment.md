# Deployment runbook

## Existing resources

Reuse public GitHub `UmitVice/evidencedesk`, Vercel Hobby projects `evidencedesk-web` (root `apps/web`) and `evidencedesk-api` (root `apps/api`). Both have Git integration, master as Production, and Ohio `cle1` functions. Keep dev previews protected and paired only with the dev API.

The account is `umitvice@gmail.com`. EvidenceDesk uses the separate console-managed Neon Free organization `org-divine-wind-27513562`, name `EvidenceDesk`. Production project: `flat-frost-26354813` (`evidencedesk-production`). Development project: `cold-mode-47834829` (`evidencedesk-dev`). Both are AWS Ohio, PostgreSQL 17.11, pgvector 0.8.0, fixed 0.25 CU, with automatic idle suspension. Never add these databases to the existing Vercel-managed Neon Launch installation or change that installation's billing plan.

Production: https://evidencedesk-web.vercel.app and https://evidencedesk-api.vercel.app. Development: https://evidencedesk-web-git-dev-umitvices-projects.vercel.app and https://evidencedesk-api-git-dev-umitvices-projects.vercel.app. Keep development and production data/credentials separate.

## Credentials and database

Existing credentials are stored locally in ignored mode-0600 environment/DSN files. Do not ask for passwords without an authentication failure, print values, put credentials in command arguments, or publish private files. The runtime uses each project's `-pooler` Neon hostname with the restricted `evidencedesk_app` login. Local maintenance uses that project's direct administrative connection. Administrative `MIGRATION_DATABASE_URL` is never deployed.

The connector enforces `sslmode=verify-full` and the pinned certifi Mozilla CA bundle for Neon hosts. Both certificate trust and hostname validation are required. Prepared statements remain disabled, and transaction-local statement/lock timeouts remain bounded. The runtime has no superuser/create-role/create-database/RLS-bypass authority, no public-schema creation, no corpus writes, and no proposal-content updates. Only private schema `evidence` is used; no Neon Auth or Data API was enabled for this migration.

Run only pending checksum-verified migrations from trusted local maintenance configuration. Never migrate or seed during imports, startup, or web requests. Do not alter applied migrations, truncate production, or run integration tests against it. All 24 real BGE chunks were copied with their model/pooling/preprocessing/version manifest and exact vectors; no new provider embedding calls or fixture substitutions were used. Future production live ingestion still requires the explicit `--allow-production` flag and a verified provider smoke receipt. Model/dimension/pooling/preprocessing/version/content hashes must continue to prevent fixture/live mixing.

Former Supabase sources `xjizbcmayuojydvwykfu` and `vgeyikjybphzrrarcwaj` are manually paused and retained with local snapshot backups under the provider restore window. Their runtime role membership was removed to fence source writes before copying. See [migration verification and rollback](neon-migration.md); after Neon writes begin, reconcile new writes before restoring the old source. The bundled Supabase public CA remains solely for legacy recovery connections.

## Environment scopes

API server-only: DATABASE_URL, SERVICE_KEY, ENVIRONMENT, AI_MODE, AI_ENABLED, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, and the existing voice-provider configuration. Production uses `production` / `live`; dev uses `development` / `live` with branch-specific Preview values. This migration changes only each environment's DATABASE_URL. Missing configuration remains a clear error, not a fallback.

Web server-only: API_ORIGIN, matching SERVICE_KEY, APP_ORIGIN. Production origins use the public aliases above. The dev branch uses its exact stable web alias for Origin checks. Task previews use their own VERCEL_URL. The protected dev API uses its existing automation bypass credential through the explicit dev-only server variable `API_PROTECTION_BYPASS_SECRET`. Do not use the platform's web-project `VERCEL_AUTOMATION_BYPASS_SECRET` as the upstream API credential. Never disable deployment protection globally or introduce NEXT_PUBLIC secrets.

After changing scoped values, redeploy. Verify actual Git SHA, aliases, function region, BFF session creation, real retrieval/generation, citations, note decisions, and persistence. Keep production and preview service credentials distinct. A READY result alone does not prove the application is functional. The Python deployment includes its tokenizer/public CA assets and certifi dependency; it excludes private files and migration tooling. The web build requires no cloud credentials.

## Workers AI and quotas

Use the existing free Cloudflare account and scoped Workers AI Read/Edit token. No Worker, paid AI Gateway, second provider, local LLM, or GPU is required. Models: `@cf/baai/bge-small-en-v1.5` (384 dimensions, cls, actual tokenizer cap 512) and `@cf/meta/llama-3.1-8b-instruct-fast`.

The support-v3 generation contract uses JSON-object mode and the schema in the system prompt. Always retain strict Pydantic validation, exact quote/source authorization, immutable proposals, bounded deadlines, and no live-to-fixture fallback. Real request failures remain visible.

The account's shared free allowance is 10,000 Neurons/day. Application limits are two analyses/minute, ten daily attempts/session, forty/environment by default. Maintenance and retries reserve budget before calls. Stop on quota errors; do not reset counters or change identities to extend live evaluation. AI_ENABLED=false is the kill switch. Cleanup is a bounded explicit maintenance command, not keepalive traffic.

## Development and release

The isolated Neon development and production projects each contain the original five migrations, separate restricted runtime credentials, and 24 real BGE chunks. API database secrets are scoped to their own environment; dev never receives production credentials/state. Other task previews receive neither development database access nor the dev-only API automation secret.

For each task: inspect Git state and reconcile divergence safely. When master/dev are synchronized, create one work branch from master. Use incremental English Conventional Commits and scan staged content before each commit and publication. Merge/push to dev, verify CI and the paired dev deployments, then fast-forward master and verify production. Keep the work branch locally and remotely. Never force push, discard unrelated work, move existing tags, or delete deployment history.

The bounded hosted browser check in `playwright.hosted.config.ts` uses exactly two explicit live analyses per run, with no retries. Set `HOSTED_URL` to the existing dev or production web origin and run `npx playwright test --config playwright.hosted.config.ts`. For protected dev, `HOSTED_AUTH_FILE` may point to an ignored mode-0600 JSON file with `origin` and existing automation `headers`; the test scopes headers to that exact origin, never page JavaScript or URLs. Traces/videos are disabled to avoid recording access credentials. Check existing daily capacity first; never change quota counters or deployment protection. This is functional verification, not a new model-quality evaluation.
