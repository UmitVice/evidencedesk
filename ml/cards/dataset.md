---
license: mit
language:
  - en
  - tr
task_categories:
  - text-generation
  - question-answering
tags:
  - rag
  - grounded-generation
  - citations
  - abstention
  - prompt-injection
  - distillation
  - synthetic
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train.jsonl
      - split: validation
        path: data/valid.jsonl
---

# EvidenceDesk grounded-support SFT

Supervised fine-tuning data for a support copilot that must answer **only** from retrieved
passages, cite verbatim quotes, abstain when evidence is missing or unresolved, and ignore
instructions injected into tickets or documents. It was used to train
[UmitVice/evidencedesk-gemma-4-12b-lora](https://huggingface.co/UmitVice/evidencedesk-gemma-4-12b-lora).
Code: [github.com/UmitVice/evidencedesk](https://github.com/UmitVice/evidencedesk).

| Split | Examples | English | Turkish | Products |
| --- | --- | --- | --- | --- |
| train | 514 | 456 | 58 | 8 |
| validation | 104 | 64 | 40 | 2 held out (FlagForge, Fatura Bulutu) |

## Format

Each line of `data/*.jsonl` is a chat in the exact serving format:

- `system`: the production EvidenceDesk prompt (`support-v3`) and the answer JSON schema.
- `user`: JSON with the ticket, the agent question, and up to four evidence passages
  (`source_id`, title, heading, version, status, passage).
- `assistant`: compact JSON, either cited claims plus a proposed internal note, or
  `{"status":"insufficient_evidence","claims":[],"proposed_note":null}`.

`data/*.meta.jsonl` carries, line by line, the product, language, behavior, expected status,
number of claims, and context chunk IDs. `corpus/` holds the synthetic help-center articles.

## Behaviors

| Behavior | Expected status | Train | Validation |
| --- | --- | --- | --- |
| answerable | answered | 308 | 56 |
| obsolete vs current version | answered | 39 | 8 |
| legitimate question with an injected document in context | answered | 27 | 6 |
| unresolved / draft policy | insufficient_evidence | 30 | 6 |
| unknown topic | insufficient_evidence | 46 | 12 |
| another customer's private data | insufficient_evidence | 24 | 6 |
| injection in the user's message | insufficient_evidence | 24 | 6 |
| request to follow an injected document | insufficient_evidence | 16 | 4 |

## How it was built

1. **Corpus.** Gemma 4 26B-A4B (QAT, 4-bit, llama.cpp) wrote help centers for ten fictional
   products, each with standard articles, a retired and a current version of one policy, an
   unresolved policy note, support boundaries, and an imported document carrying a prompt
   injection. Two products are Turkish.
2. **Tickets.** The teacher wrote tickets per article and behavior; injection and cross-tenant
   tickets come from templates.
3. **Context.** Articles are chunked with the production chunker; BM25 retrieves up to four
   passages and the target passages are guaranteed for answerable cases.
4. **Answers.** The teacher answers with the production prompt and grammar-constrained JSON
   whose `source_id` enum is limited to the retrieved passages.
5. **Filtering.** An answer is kept only if it passes the production validators (strict
   schema, citations to retrieved passages, every quote verbatim in its passage), matches the
   expected status, and does not cite the injected document. 87% of answers were kept.

## Contamination and limitations

All products, tenants, and facts are fictional. RelayNest, the product in the EvidenceDesk
evaluation set, is not in this data, and an 8-gram overlap check against the evaluation
questions removed nothing. Labels come from the generation recipe, not human review, and
"answered" targets are teacher outputs that passed automatic checks; they can still be
incomplete. Turkish coverage is small.
