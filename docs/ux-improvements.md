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

## Implemented and verified locally

- Retained the paper/teal visual character and three routes. Added active
  navigation and a distinct workspace page title.
- The landing page explains AI assistance, fictional data, the approval
  boundary, and the four-step journey beside the sample list.
- Mobile Analyze is visible without scrolling at 375 × 812. The decision
  follows sources and precedes saved notes in both visual and keyboard order.
- AI drafts, original passages, and approved notes have distinct labels and
  surfaces. Source controls name the document; source integrity is never
  presented as an answer-quality guarantee.
- Source loading/error/retry stays in the native drawer. Escape and both tab
  directions retain/restore focus; completion moves focus to the new result.
- Expiry updates while a draft is open. Approval response loss preserves the
  draft and offers a read-only refresh; a real database test of that journey
  recovers exactly one saved note without another decision request.
- Optional questions, draft/source metadata, and decision history remain
  available through native disclosures. The evaluation page summarizes
  existing records without changing or inventing model-quality results.

Local release checks at implementation `46349f2`: lint, TypeScript, optimized
production build, Python lint/types, **44 real PostgreSQL/API tests** with no
skips, **22 Chromium browser tests**, API-contract drift, npm/pip audits, staged
secret scan, and full Git-history scan passed. Automated axe checks found no
violations of the selected WCAG A/AA rules on all three pages, the draft,
source dialog, and saved state. Manual browser inspection covered desktop and
mobile. Responsive checks cover 320, 375, 768, and 1440px; keyboard and reduced
motion checks pass. Automated checks are not a claim of complete accessibility
certification or a human usability study.

The local browser suite uses the supported development server and an isolated
native PostgreSQL fixture database. An additional `next start` attempt correctly
rejected the local HTTP upstream under the existing production HTTPS guard;
no guard was relaxed. Production runtime behavior is verified on hosted HTTPS.

## Before and after captures

These are genuine screenshots from the running local fixture app, with the
simulated-mode label visible. Baseline is `cd0869f`; after is `46349f2`. No live
model-quality result is inferred from these images. Normal test runs now write
to ignored `test-results`; refresh the reviewed captures explicitly with
`SCREENSHOT_DIR=docs/screenshots npm run test:browser`.

| View | Before | After |
| --- | --- | --- |
| Desktop landing, 1440px | [Before](screenshots/ux-before/landing-1440.png) | [After](screenshots/landing-1440.png) |
| Mobile landing, 375px | [Before](screenshots/ux-before/landing-375.png) | [After](screenshots/landing-375.png) |
| Desktop saved note, 1440px | [Before](screenshots/ux-before/workspace.png) | [After](screenshots/workspace.png) |
| Mobile pending review, 375px | [Before](screenshots/ux-before/workspace-375.png) | [After](screenshots/workspace-375.png) |
| Mobile source, 375px | [Before](screenshots/ux-before/evidence-375.png) | [After](screenshots/evidence-375.png) |

[Mobile ready to analyze](screenshots/workspace-ready-375.png) ·
[Loading](screenshots/analysis-loading.png) · [Error](screenshots/analysis-error.png)

## Hosted release checks

Use the existing [protected dev](https://evidencedesk-web-git-dev-umitvices-projects.vercel.app)
and [production](https://evidencedesk-web.vercel.app) projects, paired with their
existing isolated APIs/databases. Verify exact deployment revisions and CI,
then run the bounded browser smoke on dev before promoting master. The smoke
covers two real generations, original quote inspection, exact approval and
refresh persistence, rejection without a note, secure session cookies, mobile
reflow, and automated accessibility. Record actual CI/deployment identifiers
and outcomes in the final delivery receipt; do not treat a READY deployment
alone as functional verification.
