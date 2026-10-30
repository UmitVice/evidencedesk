# Deployment runbook

## Existing resources

Reuse public GitHub `UmitVice/evidencedesk`. The web BFF is the Netlify Free site `evidencedesk-web` (workspace `apps/web`, config `apps/web/netlify.toml`), published from a local master checkout with `npx netlify-cli deploy --build --prod --filter @evidencedesk/web`. The API is the Render Free web service `evidencedesk-api` in Ohio (blueprint `render.yaml`, root `apps/api`), deployed from master on demand. Free Render instances sleep after 15 idle minutes, so the first request afterwards waits for a cold start. There are no dev or preview deployments. The former Vercel projects only redirect their `*.vercel.app` aliases to the domains below.

The account is `umitvice@gmail.com`. EvidenceDesk uses the separate console-managed Neon Free organization `org-divine-wind-27513562`, name `EvidenceDesk`. Production project: `flat-frost-26354813` (`evidencedesk-production`). Development project: `cold-mode-47834829` (`evidencedesk-dev`). Both are AWS Ohio, PostgreSQL 17.11, pgvector 0.8.0, fixed 0.25 CU, with automatic idle suspension. Never add these databases to the existing Vercel-managed Neon Launch installation or change that installation's billing plan.

Production: https://evidencedesk.umitvice.com (web) and https://api.evidencedesk.umitvice.com (API), both DNS-only CNAMEs in the `umitvice.com` Cloudflare zone; `evidencedesk-web.netlify.app` redirects to the web domain. The former dev deployments and the `evidencedesk-dev` Neon project are retired; testing happens locally.

## Credentials and database

Existing credentials are stored locally in ignored mode-0600 environment/DSN files. Do not ask for passwords without an authentication failure, print values, put credentials in command arguments, or publish private files. The runtime uses each project's `-pooler` Neon hostname with the restricted `evidencedesk_app` login. Local maintenance uses that project's direct administrative connection. Administrative `MIGRATION_DATABASE_URL` is never deployed.

The connector enforces `sslmode=verify-full` and the pinned certifi Mozilla CA bundle for Neon hosts. Both certificate trust and hostname validation are required. Prepared statements remain disabled, and transaction-local statement/lock timeouts remain bounded. The runtime has no superuser/create-role/create-database/RLS-bypass authority, no public-schema creation, no corpus writes, and no proposal-content updates. Only private schema `evidence` is used; no Neon Auth or Data API was enabled for this migration.

Run only pending checksum-verified migrations from trusted local maintenance configuration. Never migrate or seed during imports, startup, or web requests. Do not alter applied migrations, truncate production, or run integration tests against it. All 24 real BGE chunks were copied with their model/pooling/preprocessing/version manifest and exact vectors; no new provider embedding calls or fixture substitutions were used. Future production live ingestion still requires the explicit `--allow-production` flag and a verified provider smoke receipt. Model/dimension/pooling/preprocessing/version/content hashes must continue to prevent fixture/live mixing.

Former Supabase sources `xjizbcmayuojydvwykfu` and `vgeyikjybphzrrarcwaj` are manually paused and retained with local snapshot backups under the provider restore window. Their runtime role membership was removed to fence source writes before copying. See [migration verification and rollback](neon-migration.md); after Neon writes begin, reconcile new writes before restoring the old source. The bundled Supabase public CA remains solely for legacy recovery connections.

## Environment scopes

API server-only: DATABASE_URL, SERVICE_KEY, ENVIRONMENT, AI_MODE, AI_ENABLED, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, and the existing voice-provider configuration. Production uses `production` / `live`; local development uses `development` with `simulated` or `live`. This migration changes only each environment's DATABASE_URL. Missing configuration remains a clear error, not a fallback.

Web server-only: API_ORIGIN, matching SERVICE_KEY, APP_ORIGIN. Production origins use the public aliases above. `API_PROTECTION_BYPASS_SECRET` is only needed if a protected API is ever deployed again; production does not use it. Never disable deployment protection globally or introduce NEXT_PUBLIC secrets.

After changing scoped values, redeploy. Verify actual Git SHA, aliases, function region, BFF session creation, real retrieval/generation, citations, note decisions, and persistence. Keep production and preview service credentials distinct. A READY result alone does not prove the application is functional. The Python deployment includes its tokenizer/public CA assets and certifi dependency; it excludes private files and migration tooling. The web build requires no cloud credentials.

## Workers AI and quotas

Use the existing free Cloudflare account and scoped Workers AI Read/Edit token. No Worker, paid AI Gateway, second provider, local LLM, or GPU is required. Models: `@cf/baai/bge-small-en-v1.5` (384 dimensions, cls, actual tokenizer cap 512) and `@cf/meta/llama-3.1-8b-instruct-fast`.

The support-v3 generation contract uses JSON-object mode and the schema in the system prompt. Always retain strict Pydantic validation, exact quote/source authorization, immutable proposals, bounded deadlines, and no live-to-fixture fallback. Real request failures remain visible.

The account's shared free allowance is 10,000 Neurons/day. Application limits are two analyses/minute, ten daily attempts/session, forty/environment by default. Maintenance and retries reserve budget before calls. Stop on quota errors; do not reset counters or change identities to extend live evaluation. AI_ENABLED=false is the kill switch. Cleanup is a bounded explicit maintenance command, not keepalive traffic.

## OpenAI generation (optional, paid)

The always-on production path can generate with OpenAI GPT-6 Luna while retrieval stays unchanged: Cloudflare embeddings, pgvector, hybrid ranking, the same `support-v5` prompt, and the same schema/citation validators. This is the one deliberate exception to the free-services rule. It is paid per token from a prepaid OpenAI balance:

- A dedicated OpenAI project (`evidence-desk`) holds the key and has a hard monthly spend limit of $5. Auto-reload stays off, so the balance is never topped up automatically.
- At about 1,300 input and 100 output tokens per analysis, the forty-per-day environment cap bounds spend to cents per day.
- Requests use strict structured outputs with an OpenAI-compatible schema (a single root object, source IDs limited to the retrieved passages) and `store: false`.
- A 429 from the spend limit, a timeout, or an outage falls back to Cloudflare Llama 3.1 8B when `GENERATION_FALLBACK=true`. The answer badge and run trace name the model that actually answered.

Add to the Render secret file `evidencedesk.env`, then redeploy:

```sh
GENERATION_PROVIDER=openai
GENERATION_API_KEY=<key from the evidence-desk OpenAI project>
GENERATION_FALLBACK=true
```

Leave `GENERATION_BASE_URL` and `GENERATION_MODEL` unset to use `https://api.openai.com/v1` and `gpt-6-luna`. Locally, `python3 scripts/enter-local-secret.py openai` stores the key in the ignored `.env` without echoing it. Setting `GENERATION_PROVIDER=cloudflare` returns to the free path.

## Answer checks and flagged-answer review

Live answers get deterministic review flags (method and calibration in
[answer checks](../reports/answer-checks.md)). The evaluation page shows seven-day counts from
`GET /quality/summary`, which returns no ticket or answer content. To read the flagged answers
themselves, store the production runtime connection string once with
`python3 scripts/enter-local-secret.py review-database` (input hidden, written to the ignored
`.env`), then run `npm run review:flags`; it writes `.local/review/flagged.html` and opens it in the browser when anything is flagged. Without
`REVIEW_DATABASE_URL` the command reads the local database. Never set `REVIEW_DATABASE_URL` on
the hosted API.

## Development and release

There is one permanent branch, master, and it is production. For each task:

1. Inspect Git state, then create one work branch from master.
2. Commit incrementally with English Conventional Commits, scanning staged content before each commit and publication.
3. Verify locally:
   - lint, type checks, unit tests, and real PostgreSQL integration tests. Run `uv run --python 3.12 --with pgserver==0.1.4 scripts/local-pgserver.py` when Docker is not available;
   - the web build and browser checks against the local app;
   - when generation or retrieval changes, a live evaluation on a local `evidencedesk_eval*` database.
4. Before merging code that needs them, run the pending checksum-verified migrations and live ingestion against production from the trusted local maintenance configuration. Use `--allow-production` and the provider smoke receipt.
5. Merge into master and push. Deploy the API with `render deploys create srv-dbehconavr4c73aucb8g` (the service uses the public repository URL, so pushes do not deploy it), then publish the web from master with the Netlify command above.
6. Verify production: Git SHA, aliases, region, health, a real analysis with citations, a note decision, and persistence.

Keep the work branch locally and remotely. Never force push, discard unrelated work, move existing tags, or delete deployment history.

The bounded hosted browser check in `playwright.hosted.config.ts` uses exactly two explicit live analyses per run, with no retries. Set `HOSTED_URL` to the production web origin and run `npx playwright test --config playwright.hosted.config.ts`. For protected dev, `HOSTED_AUTH_FILE` may point to an ignored mode-0600 JSON file with `origin` and existing automation `headers`; the test scopes headers to that exact origin, never page JavaScript or URLs. Traces/videos are disabled to avoid recording access credentials. Check existing daily capacity first; never change quota counters or deployment protection. This is functional verification, not a new model-quality evaluation.
