### Request flow

1. **Session and quotas.** Each visitor gets an isolated sandbox session with three sample tickets.
   Per-session, per-minute, and per-environment budgets are enforced in PostgreSQL.
2. **Hybrid retrieval.** PostgreSQL full-text search and exact cosine search over bge-small
   vectors, fused with reciprocal rank fusion. Every query is scoped to the session's tenant.
3. **Grounded generation.** A fine-tuned Gemma 4 12B receives the ticket, the question, and up
   to four passages, all marked as untrusted data. It must return strict JSON: either cited
   claims plus a proposed note, or `insufficient_evidence`.
4. **Validation.** Pydantic schema checks, then every citation must reference a retrieved
   passage and every quote must appear verbatim in it. Anything else fails closed.
5. **Human approval.** The proposed note is stored with a content hash, ticket version, and
   expiry. Approval saves the exact reviewed text once, in one transaction, and writes an audit
   event. Retries replay the result instead of creating a duplicate.

### The model

`google/gemma-4-12B-it-qat-q4_0-unquantized` with a LoRA adapter trained on Apple Silicon (MLX).
Training data was distilled from Gemma 4 26B-A4B on ten fictional products, two of them in
Turkish, and filtered with the production validators. RelayNest, the product in this demo and
in the evaluation set, was never used for training.

### Limits

Citation integrity is not semantic correctness, so a human still reviews every note. The
evaluation set is a 40-case regression corpus, not a market benchmark.
