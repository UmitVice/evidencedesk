# EvidenceDesk engineering rules

- Build only the three-page support copilot and bounded Python RAG workflow. English everywhere.
- Follow `docs/implementation.md` and inspect Git state before resuming. Preserve unrelated work.
- Permanent branches: master and dev. Exactly one temporary task branch, created from validated dev; validate, commit, merge, delete before the next slice. No parallel writers, force pushes, or fabricated results.
- Use Conventional Commits. Inspect staged files and scan secrets before commits and publication.
- Keep credentials server-only. Authorize every record by session and tenant. Model output cannot execute mutations.
- Approvals apply immutable persisted content in a short, concurrency-safe database transaction. No database transaction during provider calls.
- Use genuinely free project-specific cloud resources only. Never change billing or unrelated resources.
- Run lint, type checks, unit and real PostgreSQL tests, build, browser checks, and security checks before release. Distinguish fixture checks from live model evaluation.
