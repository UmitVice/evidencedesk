# Free deployment runbook

## Verified and pending

Vercel CLI account `umitvice`, team `umitvices-projects`, billing plan `hobby` verified. Created `evidencedesk-api` (FastAPI, root `apps/api`) and `evidencedesk-web` (Next.js, root `apps/web`, Node 24.x). Public `UmitVice/evidencedesk` was created through the authenticated browser with no starter commit. GitHub CLI authentication and pushes remain blocked. Supabase and Cloudflare require browser sign-in. No production database or live model execution is verified. API preview health was verified at https://evidencedesk-pw8wuatus-umitvices-projects.vercel.app/health with supported Vercel protection bypass. The initial web deployment is available at https://evidencedesk-web.vercel.app. Vercel promoted the first web deployment to Production despite the CLI preview target; this was a static/unconfigured deployment, not a database-backed release. Subsequent final deployment receipts must identify the actual target.

## Database

Use Supabase Free only. Inspect free slots first: two project slots permit dev and master databases; one slot means local development and hosted production, with the remote development API intentionally unavailable. Do not delete existing projects or change billing.

Create a project-specific database with a strong generated password through the secure dashboard flow. Copy the migration connection and transaction-pooler connection into secret storage, not chat or shell arguments. Run version queries (`SHOW server_version`; `SELECT extversion FROM pg_extension WHERE extname='vector'`) and record actual hosted values in versions.md. Run migrations once, then seed fixtures or explicit validated live ingestion using the separate migration connection. Never run migrations or seed from a web request, import or startup.

Create a dedicated LOGIN role with a securely set password, grant membership in the migration-created `evidencedesk_runtime` group, and use that login in DATABASE_URL. Ensure the runtime role cannot create roles, databases, or schemas. Keep `evidence` outside exposed Data API schemas. Use the owner only for MIGRATION_DATABASE_URL in a trusted local maintenance environment; do not put migration credentials in Vercel runtime variables.

Run `python -m evidencedesk.cli provider-smoke` in development to record a real provider contract receipt. Production live ingestion requires `python -m evidencedesk.cli ingest-live --allow-production --smoke-receipt reports/provider-smoke.json`. The command verifies the exact model/embedding manifest receipt, reuses unchanged embeddings, reserves budget before external calls, and persists each completed corpus update transactionally. Use production-specific database connections; never point production at the evaluation database. Production activation remains blocked pending provider smoke and database credentials.

## Vercel environment pairing

Set master as each project's Production Branch after connecting the GitHub repository. dev is Preview; task-branch previews, if enabled, may only use development resources. Do not create another permanent environment. Keep production and preview service credentials distinct.

API server-only variables: DATABASE_URL (runtime transaction pooler), SERVICE_KEY (random 32+ characters), ENVIRONMENT (`production` or `development`), AI_MODE (`simulated` or `live`), AI_ENABLED, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN. Default fixture mode is explicit; there is no failure fallback from live to fixtures. No database yields a clear 503.

Web server-only variables: API_ORIGIN (matching environment's API origin, no path), SERVICE_KEY (same as matching API), APP_ORIGIN (exact frontend origin), and, only if needed, VERCEL_AUTOMATION_BYPASS_SECRET for the matching protected preview API. Never expose these through NEXT_PUBLIC variables. For dynamically named previews, omit APP_ORIGIN so the server uses VERCEL_URL; stable dev aliases require their exact origin. Vercel documents protection bypass at https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation.

Use `vercel link --project evidencedesk-api`, then `vercel deploy --target preview` from the repository root. Link the same root to evidencedesk-web and deploy again. Root-directory settings preserve the shared npm lockfile and app-local Python pyproject/uv.lock. Inspect actual build logs. Configure Git integration only to this repository. Do not deploy production until the release checks and critical review pass. Do not disable preview protection globally.

Both apps build without cloud secrets. Ignore `.env*`, `.local`, virtual environments and caches on upload. The deployed Python app requires its tokenizer asset but not CLI corpora/evaluation data; verify bundle exclusions in the actual build. No migration credentials belong in a function bundle.

## Cloudflare

Use the existing Free Workers AI account and a narrowly scoped Workers AI API token, stored server-only. No Worker deployment or paid AI Gateway is needed. Verify the candidate model with a real 10-case capped smoke before claiming live support. BGE small uses cls pooling consistently for documents and queries. Live embeddings are 384-dimensional and input is capped at 512 actual tokenizer tokens. The generation model candidate and exact JSON REST contract are in providers.py; account availability remains unverified.

The account's shared free allowance is 10,000 Neurons/day, independent of app request counters. Stop on provider quota errors. Never add billing or claim token usage is an exact neuron balance. Use AI_ENABLED=false as the kill switch. Periodically run the bounded cleanup command; do not send quota-avoidance keepalive traffic.

## Release

Run README checks, inspect staged files and history for secrets, push each validated branch and verify CI. Fast-forward master from validated dev, publish tag v0.1.0 only after release gates, deploy paired production revisions, and verify actual URLs and database behavior. Return to clean dev. If authentication prevents remote operations, preserve local commits and report GitHub CI/release as blocked.
