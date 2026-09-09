# Verified stack

Verified 2026-09-09 using official npm registry `/PACKAGE/latest` and PyPI `/pypi/PACKAGE/json` metadata. Exact dependency resolution is recorded in `package-lock.json` and `apps/api/uv.lock`. No forced peer resolutions.

| Component | Selected |
| --- | --- |
| Node | 24.21.0 local/CI target; Vercel 24.x patch managed by platform |
| Next / eslint-config-next | 16.3.4 |
| React / React DOM / React types | 19.3.0 |
| TypeScript | 7.0.2 |
| Tailwind / PostCSS integration | 4.3.3 |
| ESLint | 9.39.5 compatibility fallback |
| Playwright | 1.63.0 |
| Node types | 22.20.2 (registry latest; compatible subset) |
| Python | 3.13.15 via verified actions/python-versions in CI; local 3.13.14; Vercel selects supported 3.13 patch |
| FastAPI / Pydantic | 0.141.1 / 2.13.5 |
| Pydantic Settings / HTTPX | 2.15.0 / 0.28.1 |
| Psycopg / Python pgvector | 3.3.5 / 0.5.0 |
| LangGraph core | 1.2.11 |
| Tokenizers / Uvicorn | 0.23.2 / 0.52.4 |
| Ruff / Pyright / pytest / pip-audit | 0.16.6 / 1.1.413 / 9.1.1 / 2.10.1 |
| Local PostgreSQL / pgvector | Homebrew published 17.11 / 0.8.6; actual server query pending |
| Hosted PostgreSQL / pgvector | Not provisioned; actual versions unverified |

Sources: [npm](https://registry.npmjs.org/next/latest), [PyPI](https://pypi.org/project/fastapi/), [Node release index](https://nodejs.org/dist/index.json), [Python release](https://www.python.org/downloads/release/python-31315/), [Next support](https://nextjs.org/support-policy), [pgvector](https://github.com/pgvector/pgvector), [container tag](https://hub.docker.com/v2/repositories/pgvector/pgvector/tags/pg17).

## Deployment constraints

[FastAPI preset](https://vercel.com/docs/frameworks/backend/fastapi): `apps/api/main.py` exports `app`; app-local pyproject/uv.lock. [Hobby](https://vercel.com/docs/plans/hobby) is limited to personal non-commercial use. Use two projects and two logical environments, never production secrets in previews.

[Supabase Free](https://supabase.com/pricing): two active project slots, 500 MB each, inactivity pause possible. Check actual account capacity before provisioning. [Transaction pooler](https://supabase.com/docs/guides/database/connecting-to-postgres): disable prepared statements; separate migration connection.

[Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/): 10,000 shared account Neurons daily on Free, not 10,000 requests. No billing changes authorized. [Generation candidate](https://developers.cloudflare.com/workers-ai/models/llama-3.1-8b-instruct-fast/) and [JSON mode](https://developers.cloudflare.com/workers-ai/features/json-mode/) inspected. Live smoke and account eligibility remain blocked by authentication. [BGE small](https://developers.cloudflare.com/workers-ai/models/bge-small-en-v1.5/): 384 dimensions and 512 tokens; explicit pooling and tokenizer validation required before live ingestion.

ESLint 10.10.0 failed Next React plugin rule loading (`getFilename` removed). 9.39.5 passes the same rules; its registry deprecation is a documented tooling limitation. Node 24.21.0 downloaded with official SHA-256 verification. Local database queries confirm PostgreSQL 17.11 (Homebrew), vector 0.8.6.

Vercel build verification: its uv 0.10.11 could not resolve a 3.13.14 patch pin. Using `.python-version` = `3.13` succeeded. CI installs exact 3.13.15 using pinned actions/setup-python; that version is present in the official actions/python-versions manifest. Prettier 3.9.6 was verified from npm and pins formatting for generated contracts.

Security tooling: Gitleaks 8.30.1 installed from the verified Homebrew bottle; pinned gitleaks-action revision and GITLEAKS_VERSION in CI. Personal-account repositories do not require an action license key. Comments and extra artifact upload are disabled.

Hatchling 1.32.0 build backend verified on PyPI and pinned. Database timeouts use transaction-local SET, avoiding persistent session settings on the transaction pooler; see https://supabase.com/docs/guides/database/postgres/timeouts. Hosted pooler connectivity still requires live verification.
