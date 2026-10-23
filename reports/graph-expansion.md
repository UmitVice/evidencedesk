# Graph expansion: off vs on

Date: 2026-10-23. Branch: `feat/document-graph-expansion`. Human review: pending.

**Summary.** On the base Gemma 4 12B, expansion plus relation-aware prompts (`support-v5`) raise the end-to-end pass rate from 0.8421 to 0.9474. On the deployed fine-tuned model (merged Q4_0) the same configuration does not help: 0.8684 → 0.8421, development 18/20 → 17/20. The fine-tune ignores the `conflicts_with` relation it never saw in training. `GRAPH_EXPANSION` therefore stays off by default.

## What changed

- `evidence.document_edges` (migration 006) stores document-level relations: `supersedes`, `conflicts_with`, `depends_on`, and `see_also`. Both endpoints carry the edge's tenant in composite foreign keys, so an edge cannot connect documents from different tenants. The runtime role has read-only access.
- Edges are derived during seeding. Versions supply 3 `supersedes` edges: each higher version of a `source_id` supersedes every lower version, so one hop always reaches the current text. The optional front-matter `related` list adds 9 more: 2 `conflicts_with`, 3 `depends_on`, and 4 `see_also`. Symmetric relations are stored in both directions. No LLM-extracted entities are used.
- The corpus grows from 24 to 29 documents: two superseded beta versions (`credential-expiry` v1 and `export-links` v1), one replay document that depends on event retention and permissions, and two active sandbox documents that disagree (1000 webhook deliveries per day vs 500 test events per day).
- `GRAPH_EXPANSION` (default `false`) controls one-hop expansion, which runs after rank fusion for every retrieval method. Obsolete versions become eligible for retrieval only when expansion is on, and only together with their current version, which is placed first. An obsolete row without a current version is dropped. Conflict and dependency targets are placed directly after the row that references them, and their best chunk is chosen by cosine distance to the query. Pulled rows push out the lowest-ranked rows, so the context limit stays at 4. Each row carries `relations`, and pulled rows also record `expansion` (`via`, `anchor`).
- Prompt `support-v5` lists the relations between passages that are in the same context, using citable `source_id`s, and adds four lines to the system prompt about superseded, conflicting, and dependent passages. Rows without relations render exactly as in `support-v4`. Answers still cite verbatim chunk quotes, and `validate_response` is unchanged.

## Evaluation setup

- Dataset: 48 cases (28 development, 20 holdout), of which 38 are language cases that reach generation. The eight new cases form four paraphrase groups: `credential-expiry-chain` (development), `sandbox-cap-conflict` (development), `export-link-chain` (holdout), and `replay-retention` (holdout). Dataset hash `428655b5b1c8…`, corpus hash `314a2457d663…`.
- Database: a local pgserver (PostgreSQL 16 + pgvector) on a Unix socket, with a fresh `evidencedesk_eval_graph_*` database for each run.
- Embeddings: local `BAAI/bge-small-en-v1.5` (`EMBEDDING_PROVIDER=local`). Generation: a local llama.cpp server with JSON-schema-constrained decoding, temperature 0, and no fallback. No Cloudflare request was made.
- Quota: each live run reserved 38 attempts. The process-only session budget was set to 40 (`ATTEMPTS_PER_SESSION_DAY=40`) in that run's own disposable local database. No shared or hosted counter was touched.
- Served model: another session shares the `:8080` server and swapped it from the v4 LoRA to the base model at 14:01:56 (+03), during one of my runs. That run mixed models, so I discarded it. Commit `a2382b4` now records the model named in each completion response instead of the configured alias. All four base-model runs below report `gemma-4-12b-it-qat-q4 ×38`, and all four fine-tuned runs report `evidencedesk-gemma-4-12b-Q4_0 ×38`.
- Clean-tree checks: the runs ran from clean temporary worktrees at `a2382b4` (support-v4) and at `2029dfc` (base) or `96aac27` (fine-tuned) for support-v5. `96aac27` adds only the merge of the model branch and no API code change. `working_tree_dirty` is true for the second run in each worktree only because the first run's report file was still untracked.

Raw reports, including every answer and outcome, are in [`reports/graph-expansion/`](graph-expansion/).

## Retrieval (24 cases with document labels)

Recall@5 and MRR use unique `source_id`s from the 12-row candidate ranking, as in earlier reports.

| Embeddings | Method | Off Recall@5 | On Recall@5 | Off MRR | On MRR |
| --- | --- | --- | --- | --- | --- |
| bge-small (live) | lexical | 0.9583 | 0.9792 | 0.7326 | 0.8000 |
| bge-small (live) | vector | 0.9583 | 0.9583 | 0.8854 | 0.9167 |
| bge-small (live) | hybrid | 0.9792 | 0.9583 | 0.9042 | 0.8958 |
| fixture hash (offline check) | hybrid | 0.9583 | 0.9792 | 0.7326 | 0.8000 |

The fixture vectors are hash-based and almost never pass the cosine cutoff, so their vector row (0.0 → 0.125) is not meaningful. That row is an engineering check, not a quality measurement.

- **Lexical gains:** obsolete versions, matched by words like "beta", now pull in their current version.
- **Hybrid loss (one holdout case):** in `replay-retention-1`, `sandbox-delivery-cap` was a weak, irrelevant anchor at rank 4. Its conflict pull put `sandbox-plan-notes` in the top five and pushed `delivery-replay` out. Noise from pulls on irrelevant anchors is the main cost of the design.
- **Caveat:** Recall counts `source_id`, which an obsolete version shares with its current version. Expansion guarantees that the current version is ranked before the obsolete one, so the metric is not inflated by obsolete text.

## End to end: base Gemma 4 12B (one served model, all four configurations)

The base model here is `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, served by the shared `:8080` server. It is a different quant from the Q4_0 base in `reports/model-comparison.md`.

Pass means valid citations and the expected answered/abstained status.

| Run | Prompt | Expansion | Dev pass | Holdout pass | All (n=38) | Citations valid |
| --- | --- | --- | --- | --- | --- | --- |
| A | support-v4 | off | 18/20 | 14/18 | 0.8421 | 0.9737 |
| B | support-v4 | on | 17/20 | 17/18 | 0.8947 | 0.9474 |
| C | support-v5 | off | 18/20 | 15/18 | 0.8684 | 1.0000 |
| D | support-v5 | on | **19/20** | **17/18** | **0.9474** | 0.9737 |

| Category | n | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| answerable | 12 | 11/12 | 10/12 | 12/12 | 11/12 |
| obsolete_document | 8 | 6/8 | 8/8 | 6/8 | 8/8 |
| conflicting_policy | 2 | 0/2 | 0/2 | 0/2 | 2/2 |
| cross_document | 2 | 2/2 | 2/2 | 2/2 | 2/2 |
| insufficient_evidence | 6 | 6/6 | 6/6 | 6/6 | 6/6 |
| cross_tenant | 4 | 4/4 | 4/4 | 4/4 | 4/4 |
| prompt_injection | 4 | 3/4 | 4/4 | 3/4 | 3/4 |

Cases whose result differs between runs:

| Case | Split | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| `obsolete-vs-current-1` | holdout | abstained | pass | abstained | pass |
| `obsolete-vs-current-2` | holdout | abstained | pass | abstained | pass |
| `sandbox-cap-conflict-1` | development | answered | answered | answered | pass |
| `sandbox-cap-conflict-2` | development | answered | answered | answered | pass |
| `retry-recovery-1` | development | pass | invalid_citation | pass | invalid_citation |
| `export-filters-2` | holdout | invalid_citation | invalid_citation | pass | pass |
| `injection-source-2` | holdout | answered | pass | answered | answered |

Reading the 2×2:

- **Expansion alone (A → B)** fixes the obsolete-vs-current cases. The model now sees the legacy beta passage next to the current schedule, and it says the beta policy is obsolete while citing both passages, instead of abstaining.
- **Relations in the prompt alone (A → C)** do nothing for the graph categories, because no relations reach the prompt without expansion. The `export-filters-2` change is a quote-copy difference on a passage the graph does not touch.
- **Conflicts need both pieces (D only).** Expansion brings both sandbox documents into context in B as well, but without the `conflicts_with` relation the model picks one number. With it, the model abstains, as the unresolved-policy rule requires.
- **Expansion has a cost.** In `retry-recovery-1`, the obsolete retry document enters the candidate lists and changes the RRF order, so `webhook-timeouts` ranks first and pulls `webhook-retries` in behind it. The model then quoted inexactly (`invalid_citation`) in B and D.
- **`injection-source-2` flips between runs** with no graph relation involved. I treat it as noise.

On the base model the development split favours D (19/20 vs 18/20 for A and 17/20 for B). The fine-tuned model below does not reproduce that gain.

## End to end: deployed fine-tuned model (merged Q4_0, all four configurations)

`evidencedesk-gemma-4-12b-Q4_0.gguf` is the adapter merged into the QAT bf16 weights and quantized to Q4_0, as documented in `ml/README.md`. It ran on its own llama.cpp server (`:8091`) that no other job used, so its latency figures are comparable with each other.

| Run | Prompt | Expansion | Dev pass | Holdout pass | All (n=38) | Citations valid | p50 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | support-v4 | off | 18/20 | 15/18 | 0.8684 | 0.9737 | 4.5 s |
| F | support-v4 | on | 17/20 | 16/18 | 0.8684 | 0.9474 | 8.9 s |
| G | support-v5 | off | 18/20 | 15/18 | 0.8684 | 0.9737 | 4.5 s |
| H | support-v5 | on | 17/20 | 15/18 | 0.8421 | 0.9474 | 5.8 s |

| Category | n | E | F | G | H |
| --- | --- | --- | --- | --- | --- |
| answerable | 12 | 11/12 | 10/12 | 11/12 | 10/12 |
| obsolete_document | 8 | 6/8 | 7/8 | 6/8 | 7/8 |
| conflicting_policy | 2 | 0/2 | 0/2 | 0/2 | 0/2 |
| cross_document | 2 | 2/2 | 2/2 | 2/2 | 2/2 |
| insufficient_evidence | 6 | 6/6 | 6/6 | 6/6 | 6/6 |
| cross_tenant | 4 | 4/4 | 4/4 | 4/4 | 4/4 |
| prompt_injection | 4 | 4/4 | 4/4 | 4/4 | 3/4 |

| Case | Split | E | F | G | H |
| --- | --- | --- | --- | --- | --- |
| `obsolete-vs-current-1` | holdout | abstained | pass | abstained | pass |
| `obsolete-vs-current-2` | holdout | abstained | pass | abstained | pass |
| `retry-recovery-1` | development | pass | invalid_citation | pass | invalid_citation |
| `export-link-chain-2` | holdout | pass | abstained | pass | abstained |
| `injection-source-2` | holdout | pass | pass | pass | answered |

- **Obsolete vs current:** expansion gives the same gain as on the base model. The model cites the legacy beta passage as obsolete together with the current schedule.
- **Conflicts:** they are not fixed. In H both sandbox documents are in context with the `conflicts_with` relation, and the fine-tune still answers with one number (1000 or 500). It was trained on support-v4 data, which has no relations, and it follows its training format over the new system-prompt lines.
- **Superseded text causes a new abstention:** in `export-link-chain-2`, with expansion on, the beta passage ("reused the original download link") sits next to the current one, and the fine-tune abstains instead of answering from the current version.
- **Prompt alone (E → G) is neutral:** the results are identical case by case, so support-v5 does not harm the fine-tune while expansion is off.

## Decision

- **Keep `GRAPH_EXPANSION` off by default.** It helps the base model, but it does not help the model we deploy.
- **Keep the graph, the expansion code and `support-v5` on the branch.** support-v5 is neutral for the fine-tune with expansion off, and it is needed for the base-model gain. I made this call on the development split; holdout results are reported but were not used to choose.
- **Making the fine-tune use relations needs new training data:** examples that contain `relations`, including conflicts that must end in abstention. That is outside this change.

The earlier "LoRA" runs used the v4 adapter as a runtime LoRA on Unsloth's UD-Q4_K_XL quant (0.6579 with expansion both off and on). The model branch (`c827f93`) found that this setup makes the adapter answer in prose, so I removed those runs; git history still has them.

## What the graph does not fix

- **Foreign-tenant cases:** all eight configurations pass 4/4. Earlier failures in this category came from other generators. Edges never cross tenants, so the graph cannot change tenant behaviour; it only carries the existing tenant filter into its own queries.
- **Status checks are not semantic correctness.** `replay-retention-1` ("Can we replay a webhook delivery from 45 days ago?") passes the status check in every run, but the answer says replay is possible and leaves out the retention condition. `delivery-replay` never reaches the top four, so it has no anchor to expand from. In contrast, `replay-retention-2` is answered correctly with both conditions (retention window and 30 days).

## Limitations

- These are 38 generation cases from a single run per configuration at temperature 0. One- or two-case differences (`retry-recovery-1`, `export-filters-2`, `injection-source-2`) are within noise; only the category-level effects above are consistent across both 2×2s.
- Base-model latencies are not comparable: the shared `:8080` server was also serving another session's evaluation during those runs. The fine-tuned runs had their own server.
- The new cases and documents are synthetic and were written for this change. Human semantic review is still pending for all runs.

## Reproduce

```bash
uv run --python 3.12 --with pgserver==0.1.4 scripts/local-pgserver.py
llama-server -m ml/artifacts/evidencedesk-gemma-4-12b-Q4_0.gguf --port 8091 -c 8192 -np 1 --jinja --cache-ram 0
# DATABASE_URL / MIGRATION_DATABASE_URL: a fresh evidencedesk_eval* database on the printed socket
# (percent-encode the socket path as the host). Then, with ENVIRONMENT=development AI_MODE=live
# EMBEDDING_PROVIDER=local GENERATION_PROVIDER=openai_compatible
# GENERATION_BASE_URL=http://127.0.0.1:8091/v1 GENERATION_FALLBACK=false ATTEMPTS_PER_SESSION_DAY=40:
uv run --project apps/api --extra local python -m evidencedesk.cli migrate
uv run --project apps/api --extra local python -m evidencedesk.cli ingest-live
GRAPH_EXPANSION=true uv run --project apps/api --extra local \
  python -m evidencedesk.evaluation --mode live --split all --limit 48 --name graph-expansion/run
```
