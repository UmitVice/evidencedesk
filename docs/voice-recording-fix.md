# Hosted voice recording repair

## Problem and implementation

The browser attempted a WebSocket connection to the Next.js web origin, where no socket upgrade handler existed. The Python gateway lived in the separate API deployment. Its single-use tickets were process-local and unsuitable for reliable authentication across serverless instances; missing live voice configuration could also select a mock provider. Text/database checks from the Neon migration did not prove a working hosted microphone flow.

The deployed recording flow now uses the existing free services: record up to 30 seconds → stop and transcribe through the same-origin HTTPS BFF → review/edit transcript → explicitly analyze → inspect validated original sources → explicitly approve or reject the persisted draft. Cloudflare Workers AI Whisper (`@cf/openai/whisper-large-v3-turbo`) handles transcription with the existing scoped server token. No provider credential, session token, or socket ticket is exposed to browser code. No new service, billing change, or paid resource is required.

The browser retains playback audio only on the current page and releases microphone tracks after stopping, errors, or navigation. Uploads are normalized to mono 16-bit 16 kHz PCM WAV. Both BFF and API enforce a 960,044-byte bound; the API also validates format, duration, complete sample data, and silence before provider access. The user can retry transcription explicitly after an outage without losing playback audio. Ticket switching and parallel text operations are disabled while recording/transcribing. Failed analysis retains the established fail-closed UI; no invalid draft is made approvable.

Every transcription authorizes the ticket against the session and tenant before using the provider. Transcription consumes one existing durable environment/session/minute quota reservation, including provider failures. A subsequent analysis consumes a separate reservation. Provider calls occur outside database transactions. The same citation validators, immutable proposal content, concurrency-safe approval, and persisted-note history handle both input methods. Raw audio is not stored in PostgreSQL; the reviewed question is persisted only when analysis is requested. The privacy notice now describes the real provider processing and page-local playback accurately.

Legacy streaming adapters remain for local experimental tests. Live-mode missing-provider, database, and retrieval errors no longer return fabricated fixture output. The current hosted UI does not use those adapters.

## Verification

- Real PostgreSQL/API suite: 65 tests passed, none skipped, including cross-session rejection, size/type/duration/silence boundaries, shared quota enforcement, absence of transcript-only note/run creation, and provider failure without fixture fallback.
- Local browser regression suite: 25 tests passed. Includes native MediaRecorder/audio decoding, mocked transcription clearly labeled as a fixture, transcript review, conservative insufficient-evidence behavior, standard exact-note approval/persistence, explicit transcription retry, and microphone-denial recovery. Real provider voice verification is a separate opt-in hosted test.
- Lint, TypeScript/Python checks, build, contract regeneration, dependency audits, and secret scans are release gates.
- One bounded diagnostic used a locally synthesized spoken English question with real Cloudflare transcription; the returned text preserved the webhook recovery question. It is a transport diagnostic, not a broad speech-quality evaluation.

The hosted `tests/hosted/voice-recording.spec.ts` is opt-in using `HOSTED_VOICE_AUDIO`: it injects a spoken WAV into Chromium's microphone input, exercises the actual deployed recording/upload/transcription/RAG flow without mocking provider responses, checks all sources, approves the exact note, reloads to verify database persistence, and checks mobile reflow/accessibility. It makes one transcription and one analysis, with no automatic test retry or quota reset. Existing text approval/rejection smoke remains separate. Individual live measurements are recorded after deployment; they do not establish speech accuracy across accents/devices/languages.

## Hosted development evidence

The application revision `f7c8b970d45f006875d83802e440092b8bc475f9` passed [development CI](https://github.com/UmitVice/evidencedesk/actions/runs/36904607236). Both paired dev deployments were READY at that revision. The opt-in hosted voice check passed with real Cloudflare transcription and generation: spoken question preserved, playable recorded audio, all source drawers inspected, exact note approved and persisted after reload, 320/375/768-pixel reflow, automated accessibility, no page errors, one transcription, one analysis, and zero voice WebSocket connections.

The first hosted test invocation stopped before recording because its initial badge assertion expected “Live AI” before an analysis; the UI correctly showed “Ready for live analysis.” The test now verifies readiness first and live-result provenance after analysis. No provider call or quota reset was used to repair that assertion. Local early failures included an unsupported microphone in Chromium's older headless shell and ambiguous test selectors; the checks now use full Chromium's native recording path and scoped selectors. These were test-harness corrections, not relaxed application validators.

Production is promoted only after the dev CI/deployment/voice gates pass. The release procedure repeats the same opt-in voice check and the independent text approval/rejection smoke against the public production origin and verifies the final branch SHAs and READY aliases. Those final results are reported in the delivery evidence.

The final dev CI at `5af2c0d` additionally caught an enabled microphone button halfway through an opacity transition after approval (contrast 3.79:1). The button now transitions only background/border colors; enabled text returns immediately to full contrast. Accessibility checks remain unchanged.

## Provider documentation

- [Vercel WebSockets](https://vercel.com/docs/functions/websockets): current beta supports Python ASGI, but Next.js requires an upgrade handler and persistent authentication state must not depend on process-local memory. This repair uses bounded HTTP requests instead of introducing a new socket layer.
- [Cloudflare Whisper input and output](https://developers.cloudflare.com/workers-ai/models/whisper-large-v3-turbo/).
- [Workers AI free allowance and limits](https://developers.cloudflare.com/workers-ai/platform/pricing/): existing free allowance applies; exhausted free quotas fail closed. No upgrade or increased project budget was configured.
