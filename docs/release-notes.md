# v0.1.0 release candidate

Status: local implementation validated. Tag and GitHub release are not published; GitHub authentication and remote CI are pending.

EvidenceDesk is a three-page support copilot demonstration with an isolated anonymous ticket workspace, inspectable source excerpts, an immutable approval queue and a read-only evaluation report. It includes 24 original synthetic documents across two tenants, lexical/vector/hybrid retrieval, a bounded LangGraph workflow, a Cloudflare Workers AI adapter, atomic database quotas and concurrency-safe note approvals.

Validation: 41 Python/API/real-PostgreSQL tests and six browser tests passed; frontend/Python lint and type checks, production build, generated API contract, dependency audits and secret scans passed. The fixture report processes 40 cases and measures retrieval only. Live model smoke, semantic quality and human review remain pending.

Published web: https://evidencedesk-web.vercel.app. Published API health: https://evidencedesk-api.vercel.app/health. The hosted database is not configured: the web provides a static walkthrough and explicitly reports unavailable session creation. The full database-backed fixture flow is verified locally.

Before publishing the release: authorize GitHub CLI, push validated dev, verify CI, fast-forward master, create v0.1.0, publish these notes with refreshed deployment/verification status, and return to clean dev. Cloud database and live quality results are separate verification milestones; do not replace missing measurements with fixture claims.
