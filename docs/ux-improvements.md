# First-visit UX improvements

## User outcome

A first-time visitor can choose a fictional support ticket, request AI help,
compare a suggestion with original documentation, and approve or reject the
exact proposed internal note. The visitor understands that citations are not
a guarantee of correctness and that only approval saves a note.

## Baseline inspection

Inspected the deployed desktop and 375px mobile UI at baseline `cd0869f`.
Captured fresh screenshots from the unchanged local application using Chromium,
the existing browser tests, and a separate native PostgreSQL fixture database.
These are UI/interaction fixtures, not new live-model evaluations.

- Keep the warm neutral palette, teal controls, direct scenario links, native
  source dialog, original quotations, and exact-content decision boundary.
- Replace the abstract landing headline and technical session vocabulary with
  a brief explanation and an obvious sample-ticket starting point.
- Combine ticket context with the analyze action. Mobile currently places
  metadata above analysis and empty saved notes before the approval decision.
- Give each operation its own progress and recovery state. A source request
  currently makes the analysis button say “Working”.
- Separate AI drafts, original sources, and approved notes through labels,
  layout, and state; preserve visible limitations.

## Implementation plan

1. Clarify sample selection and active navigation without adding pages or tours.
2. Reorder the workspace around analyze, inspect, decide, and saved result;
   move optional questions and technical details into native disclosures.
3. Improve async status, errors, expiry, focus, touch targets, and mobile layout.
4. Verify complete Chromium journeys, keyboard/accessibility, responsive layouts,
   lint/types/build, real PostgreSQL tests, contract and security checks.
5. Commit incrementally, push and verify dev, then promote and verify production.

## Branch policy for this task

The user overrides the historical branch-deletion workflow. Both permanent
branches and their remote refs were synchronized at `cd0869f` before creating
`codex/first-visit-ux` from master. Use this single work branch, preserve it
locally and remotely, verify dev before promoting master, and use no parallel
writers.

## Screenshots

Fresh baseline captures are in [ux-before](screenshots/ux-before). Updated
captures and the verified release record will accompany the implementation.
