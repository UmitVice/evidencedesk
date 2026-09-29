# EvidenceDesk

**Turn a support ticket into a reviewed note.**

EvidenceDesk is a support copilot for the fictional SaaS product RelayNest. It retrieves authorized product documentation, returns structured claims with original excerpts, and proposes an internal ticket note. Only an explicit human decision can save that note.

[Live demo](https://evidencedesk-web.vercel.app) · [Evaluation record](https://evidencedesk-web.vercel.app/evaluations) · [API health](https://evidencedesk-api.vercel.app/health)

![Ticket-first sample cases](docs/screenshots/landing-1440.png)

![Investigation, saved note, and audit timeline in the local fixture demo](docs/screenshots/workspace.png)

This personal portfolio/reference project makes AI-assisted support decisions inspectable. The hosted production path uses real retrieval and Workers AI; explicit approval persists the exact reviewed note. **Human answer review remains pending.** The complete 40-case live evaluation includes validation and abstention failures. Current resources and limitations are in [implementation status](docs/implementation.md).

## Try it locally

Requirements: Node 24.x (24.21.0 pin), Python 3.13, uv, Docker Compose. Hosted accounts and AI credentials are not needed for the local fixture demo.

```sh
npm ci
uv sync --project apps/api --frozen
npm run db:up
python3 scripts/local-env.py
npm run db:migrate
npm run db:seed
npm run db:runtime
npm run api
# In another terminal:
npm run dev
```

Open http://localhost:3000. Choose a home-page scenario to open its isolated ticket directly, then select Analyze ticket, inspect evidence, and use Approve & save note or Reject draft. Refreshing preserves the pending decision or saved note. Sessions expire after 24 hours. The simulated-mode label stays visible; arbitrary fixture questions are rejected. The optional SSO question demonstrates insufficient evidence. Two analyses per minute, ten daily attempts per session, and forty per environment are the conservative defaults.

The local environment helper writes ignored mode-0600 files and never prints generated credentials. It preserves existing files. Docker exposes PostgreSQL only on loopback port 54329. The local runtime helper separates the restricted API login from the migration owner. Hosted runtime must likewise use the restricted role described in [deployment](docs/deployment.md). The integration tests run API operations as that restricted role.

## Architecture

```mermaid
flowchart LR
    subgraph Client [Browser / Next.js]
        WebUI[Workspace / Inspection UI]
        Mic[Web Audio API Mic 16kHz]
        Spk[Audio Playback 24kHz]
        Cards[Live Citation Drawer]
    end

    subgraph BFF [Next.js BFF]
        AuthProxy[HTTP Proxy / Session Cookie]
        TicketGen[POST /api/voice/ticket]
    end

    subgraph API [FastAPI Backend]
        REST[REST Endpoints]
        WS["/api/voice/session (WebSocket)"]
        VAD[Voice Activity Detection / Buffer]
        Router[Voice Session Coordinator]
    end

    subgraph Providers [AI & S2S Providers]
        CF[Cloudflare Workers AI REST]
        MockVoice[Deterministic Mock Voice Provider]
        GeminiLive[GCP Gemini 2.0 Multimodal Live API]
    end

    subgraph Storage [Authorized Storage]
        DB[(PostgreSQL + pgvector)]
    end

    WebUI --> AuthProxy --> REST --> DB
    REST --> CF
    TicketGen --> REST
    Mic -->|Linear PCM Audio| WS
    WS -->|Audio Chunks| Spk
    WS -->|Citations & Transcripts| Cards
    WS <--> VAD <--> Router
    Router <--> MockVoice
    Router <--> GeminiLive
    Router -->|RAG Tool Calls| DB
```

- 24 original Markdown documents, two synthetic tenants, three sandbox tickets.
- Real-time Voice & Speech-to-Speech (S2S) Copilot over WebSockets with frame-accurate Voice Activity Detection (VAD) and barge-in interruption.
- Dual-provider voice architecture: GCP Gemini 2.0 Multimodal Live API with standard `websockets`, paired with a zero-cost deterministic Mock Voice Provider for offline testing.
- Secure single-use voice tickets ensuring `SERVICE_KEY` remains server-only while browser streams directly via Web Audio API.
- Token-bounded, hashed ingestion; explicit 384-dimensional embedding manifests.
- PostgreSQL full-text ranking, exact cosine search, and reciprocal rank fusion.
- Strict structured answers with citation-ID and quote checks; no arbitrary model tool execution.
- Immutable, expiring proposals tied to ticket versions. One transactional note effect under retries.
- Full workspace interface: text analysis, real-time voice copilot, and read-only evaluations.

See [architecture decisions](docs/architecture.md), [OpenAPI](docs/openapi.json), and [security boundaries](SECURITY.md).

## Verification

```sh
npm run lint
npm run typecheck
npm run build
npm run check:api
# Real PostgreSQL integration: create a disposable database named evidencedesk_test first.
TEST_DATABASE_URL=postgresql://evidencedesk:local-development-only@127.0.0.1:54329/evidencedesk_test npm run check:api
npm run contract
uv run --project apps/api python scripts/api-contract.py --check
npx playwright install chromium
npm run test:browser
npm audit --audit-level=moderate
uv run --project apps/api pip-audit --skip-editable
python3 scripts/scan-secrets.py
```

Without TEST_DATABASE_URL, integration tests explicitly skip; that is not a full verification. To create the test database with Compose: `docker compose exec db createdb -U evidencedesk evidencedesk_test`. Tests guard the database name before clearing sandbox test rows. Browser tests need the local `.env` files and seeded database; Playwright starts API/UI servers if absent. CI uses standard Linux runners, a real pgvector service, pinned actions, no model or cloud database secrets, and short-lived failure artifacts.

## Evaluations

The [fixed dataset](apps/api/evals/cases.json) contains 40 grouped scenarios: 24 development, 16 holdout. The [offline report](reports/latest-offline.md) compares retrieval using deterministic fixture vectors. It does **not** measure live model or semantic answer quality. Action/provider-control cases point to separately executed engineering tests. No method is required to win.

Use a separate database named `evidencedesk_eval*`, set DATABASE_URL and MIGRATION_DATABASE_URL to it, then migrate and seed. Run `npm run eval:offline`. Never use a public production database for evaluations.

For live checks, configure server-side Cloudflare credentials in development, run the provider smoke and idempotent live ingestion, then `npm run eval:smoke`. After inspecting that ten-case run and confirming free account capacity, an explicit maintainer run can evaluate all 40 cases. The support-v3 full live suite at clean `b1943513cef15e6f42335fbf2642bf094c09217c` processed all 40 cases: 30 real generation attempts/completions and ten engineering-control references. Twenty-eight outputs passed schema/citation checks, two failed structured validation, and five valid outputs disagreed with the expected answer/abstention status. Retrieval n=16: Recall@5 1.0 for all methods; MRR lexical 0.703125, vector 0.921875, hybrid 0.875. Latency n=30: p50 1.15 s, p95 2.44 s. Human semantic review remains pending. The held-out results were measured after prompt tuning and were not used to tune the released prompt. Historical reports and the ten-case smoke remain in [reports/history](reports/history). See the [method, budgets, and review rubric](docs/evaluation.md).

### Real-Time Voice & Speech Evals

The voice pipeline includes an automated low-latency eval framework ([`apps/api/evidencedesk/voice/evals.py`](apps/api/evidencedesk/voice/evals.py)) executed against deterministic offline scenarios and live S2S streams:
- **TTFA (Time-To-First-Audio)**: Tracks audio arrival latency from turn initiation. SLA budget is p95 < 600 ms (measured at ~31 ms on local stream).
- **Barge-in / Interruption Cancellation**: Measures milliseconds to cancel assistant streaming upon user speech. SLA budget is p95 < 300 ms (measured at < 1 ms).
- **Spoken Citation Faithfulness**: 100% verification that spoken claims match retrieved Markdown excerpts without hallucinated policies.
- **Abstention Accuracy**: 100% compliance verifying that unanswerable queries explicitly abstain without fabricating guidance.

## What this project demonstrates

| Engineering area | Inspectable evidence |
| --- | --- |
| Python APIs and typed contracts | [FastAPI routes](apps/api/main.py), [contract generator](scripts/api-contract.py) |
| Bounded RAG and provider integration | [workflow](apps/api/evidencedesk/workflow.py), [retrieval](apps/api/evidencedesk/retrieval.py), [Cloudflare adapter](apps/api/evidencedesk/providers.py) |
| Real-Time Voice & S2S RAG | [WebSocket Gateway](apps/api/evidencedesk/voice/gateway.py), [VAD & Audio Framing](apps/api/evidencedesk/voice/vad.py), [Gemini & Mock Providers](apps/api/evidencedesk/voice/provider.py) |
| Voice Evals & Low-Latency SLA | [Voice Evals Framework](apps/api/evidencedesk/voice/evals.py), [Automated Voice Test Suite](apps/api/tests/test_voice.py) |
| Interactive Web Audio Streaming | [Voice Copilot Component](apps/web/app/workspace/voice-copilot.tsx), [BFF Single-Use Ticket](apps/web/app/api/[...path]/route.ts) |
| Authorization and idempotency | [approval transaction](apps/api/evidencedesk/actions.py), [SQL invariants](apps/api/migrations/003_approvals.sql), [race tests](apps/api/tests/test_actions.py) |
| Evaluation discipline | [evaluation runner](apps/api/evidencedesk/evaluation.py), [dataset checks](apps/api/tests/test_evaluations.py) |
| Cloud deployment and CI/CD | [GitHub Actions](.github/workflows/ci.yml), [Vercel/Supabase runbook](docs/deployment.md) |
| Full-stack behavior | [BFF](apps/web/app/api/[...path]/route.ts), [browser tests](tests/browser/workspace.spec.ts) |

## Deployment and limitations

Use two Vercel Hobby projects, Supabase Free PostgreSQL/pgvector, and Cloudflare Workers AI Free. No paid services, email, CRM writes, registration, training, or GPUs. [Deployment instructions](docs/deployment.md) explain environment pairing, least-privilege runtime credentials, pooler settings, provider smoke, and exact remaining setup. [Verified versions](docs/versions.md) record runtime differences and compatibility findings.

Citation integrity is not semantic correctness. Prompt injection cannot grant tools, but a plausible inaccurate answer remains possible and requires review. Expired or changed tickets need regeneration. Interrupted analysis does not resume at an arbitrary graph node. Live failures never become simulated successes. A missing database leaves the case descriptions and evaluation record available and reports session creation as unavailable. The protected dev Preview is paired with its own API and isolated Free Supabase database; it never shares production state. Free services have quotas and Supabase inactivity pauses. Cleanup is a bounded explicit command: `npm run db:cleanup`.

A [demo script](docs/demo-script.md) covers answer/source inspection, abstention, rejection, approval retries, and evaluation limitations. Screenshots are from the running local fixture app, verified at 375, 768, and 1440 px; no recording is claimed. [Before/after UX record](docs/ux-improvements.md) · [Mobile investigation](docs/screenshots/workspace-375.png) · [Claim-associated evidence](docs/screenshots/evidence-1440.png). Potential future work includes stronger semantic review and real identity integration, beyond this deliberately small scope.

Original code and synthetic data: MIT. See [third-party notices](THIRD_PARTY_NOTICES.md).
