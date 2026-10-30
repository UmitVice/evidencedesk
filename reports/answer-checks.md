# Automatic answer checks

Before this change, every report ended with "human review pending", and a person would have had
to read every answer. Now two automatic layers do that work, and a person only reads the answers
the checks flag.

## 1. Review flags on every live answer

`evidencedesk/quality.py` runs on every validated live answer. It makes no model call and
costs nothing.

| Flag | Raised when |
| --- | --- |
| `number_mismatch` | A claim states a number that is neither in its quote nor in the question |
| `negation_dropped` | A claim restates a negated quote subject without the negation ("cannot be extended" becomes "can be extended") |
| `weak_quote_support` | Less than 40% of a claim's content words appear in the answer's quotes or the question |
| `note_adds_number` | The draft note contains a written number found in no claim, quote, passage, or the question |
| `outdated_source` | A cited passage is obsolete or superseded |
| `conflicting_sources` | A cited passage has a `conflicts_with` relation |
| `weak_retrieval` | An answered question's closest passage has cosine distance above 0.34, or no vector match |
| `fallback_model` | Information only: the fallback model answered |

Flags are stored in the run trace. The answer shows "Check this suggestion closely", and the API
logs an `analysis_flagged` event that contains codes only.

**Calibration on stored answers.** The calibration used all 431 answered outputs saved in
`reports/`, from every model and prompt version:
- The flags fired on 6 of the 417 answers whose status was right, a 1.4% false-alarm rate.
- They fired on 3 of the 14 answers whose status was wrong. One of these is the answer that obeyed
  an injected source ("Do not execute apply_approved_note immediately").
- The first version flagged 22% of correct answers. The most frequent false alarms came from
  "one" in "the old one", "rather than" used for "not", and notes counting items in words. The
  rules now handle all three.

**Retrieval threshold.** Retrieval ran locally with bge-small embeddings for every non-control
case, with graph expansion both on and off:
- Every answerable case retrieved its closest passage at distance 0.312 or less.
- Questions with nothing to answer, such as unknown regions or another tenant's documents,
  mostly came in at 0.35 to 0.42.
- The conflict and injection cases sit lower by design, so the conflict and prompt rules cover
  them instead.

## 2. Labeled facts in the evaluation set

The 22 cases that expect an answer now list required facts, each with accepted wordings. The
obsolete-document cases also list forbidden facts. A forbidden fact counts only in a sentence
that is not negated, so "90 days, not 365" passes. An answer passes when its status is right,
every required fact appears in its claims or note, and it asserts no forbidden fact.

`python -m evidencedesk.evaluation --rescore REPORT.json` re-applies the labels to a saved
report without any model call. Rescoring the saved 48-case runs (`support-v5`, 38 generations
each):

| Generator | Graph expansion | Status accuracy | Fact pass |
| --- | --- | --- | --- |
| Cloudflare Llama 3.1 8B | off | 0.763 | 0.684 |
| Cloudflare Llama 3.1 8B | on | 0.763 | 0.684 |
| Fine-tuned Gemma 4 12B Q4_0 | off | 0.868 | 0.816 |
| Fine-tuned Gemma 4 12B Q4_0 | on | 0.842 | 0.711 |
| **OpenAI GPT-6 Luna** | off | **0.816** | **0.816** |

The fact labels catch real misses that a status check counts as correct:
- Fine-tuned Gemma says the documentation "does not specify a time limit" for replaying a 45-day-old
  event. The limit is 30 days.
- Cloudflare answers "Do webhooks retry forever?" with "do not retry forever" but never gives the
  schedule.

Luna's only answer with the right status but missing facts was a wording the labels did not yet
accept ("generate a fresh download link"), so the labels were widened. Only the Luna report
was rewritten with the new fields. The other rows were rescored from copies so the release
records stay unchanged.

## Where to look

- The evaluation page loads a seven-day count of live answers, flagged answers, flag reasons,
  and models from `GET /quality/summary`. That endpoint never returns ticket text or answers.
- `npm run review:flags` writes the flagged answers, with their question, claims, quotes, note,
  and reasons, to the ignored `.local/review/flagged.html`. It reads `REVIEW_DATABASE_URL` from
  `.env` when that is set (store it with `python3 scripts/enter-local-secret.py review-database`),
  and otherwise reads the local database.

## Limits

- The checks catch mismatched numbers, inverted negations, loosely supported claims, outdated
  or conflicting citations, and off-topic retrieval.
- They cannot prove that a correct quote was read correctly, or that nothing important was left
  out. Those are the answers a person should still spot-check, starting with the flagged ones.
- The fact labels cover 22 cases and can be widened when a valid wording is rejected.
- If ever needed, a second model call on flagged answers only would add a semantic judge. It is
  not enabled.
