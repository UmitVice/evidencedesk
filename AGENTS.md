# EvidenceDesk engineering rules

- Build only the three-page support copilot and bounded Python RAG workflow. English everywhere.
- Follow `docs/implementation.md` and inspect Git state before resuming. Its "Open items and handoff" section lists what is left; confirm with the maintainer before starting any of it. Preserve unrelated work.
- Talk to the maintainer in Turkish; code, commits, and documentation stay in English. Never commit on master, even if a branch prompt suggests staying on it.
- This is a portfolio project without real customers: add no scheduled jobs, keepalives, or local background processes, and stop local test servers when done.
- One permanent branch: master, which is production. There is no dev branch and no dev or preview deployment; only master is published (Netlify web, Render API). Create one work branch from master, make incremental commits, and verify everything locally (real PostgreSQL via `scripts/local-pgserver.py`, local or live model evaluation, browser checks against the local app). Then merge into master, which deploys production, and verify production. Run pending migrations and corpus ingestion against production before merging code that needs them. Keep the work branch locally and remotely. No parallel writers, force pushes, or fabricated results.
- Use Conventional Commits. Inspect staged files and scan secrets before commits and publication.
- Keep credentials server-only. Authorize every record by session and tenant. Model output cannot execute mutations.
- Approvals apply immutable persisted content in a short, concurrency-safe database transaction. No database transaction during provider calls.
- Use genuinely free project-specific cloud resources only, except OpenAI generation, which runs from the dedicated `evidence-desk` OpenAI project under its $5 hard monthly limit. Never change billing or unrelated resources.
- Run lint, type checks, unit and real PostgreSQL tests, build, browser checks, and security checks before release. Distinguish fixture checks from live model evaluation.
