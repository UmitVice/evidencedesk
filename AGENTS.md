# EvidenceDesk engineering rules

- Build only the three-page support copilot and bounded Python RAG workflow. English everywhere.
- Follow `docs/implementation.md` and inspect Git state before resuming. Preserve unrelated work.
- One permanent branch: master, which is production. There is no dev branch and no dev or preview deployment; only master is published (Netlify web, Render API). Create one work branch from master, make incremental commits, and verify everything locally (real PostgreSQL via `scripts/local-pgserver.py`, local or live model evaluation, browser checks against the local app). Then merge into master, which deploys production, and verify production. Run pending migrations and corpus ingestion against production before merging code that needs them. Keep the work branch locally and remotely. No parallel writers, force pushes, or fabricated results.
- Use Conventional Commits. Inspect staged files and scan secrets before commits and publication.
- Keep credentials server-only. Authorize every record by session and tenant. Model output cannot execute mutations.
- Approvals apply immutable persisted content in a short, concurrency-safe database transaction. No database transaction during provider calls.
- Use genuinely free project-specific cloud resources only. Never change billing or unrelated resources.
- Run lint, type checks, unit and real PostgreSQL tests, build, browser checks, and security checks before release. Distinguish fixture checks from live model evaluation.
