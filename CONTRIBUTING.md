# Contributing

Use English and focused Conventional Commits. Read AGENTS.md and docs/implementation.md before edits. Start one task branch from master, run every check locally, review, commit, and merge it into master, which deploys production. There is no dev branch or dev deployment. Never force-push or edit applied migrations.

Run `npm ci`, `uv sync --project apps/api --frozen`, then the README verification commands. Add tests for changed trust boundaries and transaction behavior. Keep generated API declarations in sync with `npm run contract`. Never tune on the holdout dataset without documenting contamination and replacing it. Never describe deterministic fixtures as live model evaluation.
