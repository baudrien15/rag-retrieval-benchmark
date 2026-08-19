# CLAUDE.md — Project instructions

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

Read this fully before writing any code.

## What this project is

A **measured benchmark** comparing three retrieval configurations for a
RAG chatbot, on a synthetic customer-support corpus.

The deliverable is **a results table with credible numbers**, not a
production chatbot. Every design decision should serve measurability.

## The single most important rule

**We are isolating retrieval as the only variable.**

Anything that varies between the three runs other than the retrieval
method invalidates the whole experiment. That means:

- Same generation model, same temperature, same prompt across all runs.
- Same chunking across all runs.
- Same test set, same order, same judge.

If you are ever tempted to "improve" something mid-experiment, stop and
ask first.

## The three configurations under test

| ID | Retrieval |
|----|-----------|
| `dense` | Dense vector search only |
| `hybrid` | Dense + sparse, fused with RRF |
| `hybrid_rerank` | Dense + sparse + reranking of the fused candidates |

## The fictional domain

**Lumen Spa & Wellness** — a fictional wellness centre offering
treatments by appointment.

This domain was chosen deliberately: it is dense in **exact terms**
(prices, treatment names, durations, cancellation windows), which is
precisely where dense-only retrieval is expected to fail.

Do not model this on any real business. All content is invented.

## Test set design

66 questions, in four categories. The category split is what makes the
final report diagnostic rather than promotional.

The first 30 are the original set and their wording and annotations are
frozen. Questions 31-66 were added with the corpus expansion and target
the confusable clusters.

| Category | Count | Purpose |
|----------|-------|---------|
| `exact_term` | 30 | Prices, treatment names, durations. Expect dense to underperform. |
| `semantic` | 15 | Paraphrase, indirect phrasing. Expect dense to do fine. |
| `multi_fact` | 12 | Answer requires two documents. |
| `out_of_scope` | 9 | No correct document exists. Correct behaviour is escalation. |

Reporting `semantic` honestly — where hybrid gives little or no gain —
is required. A table where every category improves looks fabricated.

## Metrics

Four, no more:

1. **hit@3** — is a correct document in the top 3? (pure retrieval)
1b. **hit@1** — is a correct document ranked first? Added with the
    corpus expansion: once the corpus holds clusters of near-identical
    documents, rank 1 is where "right cluster, wrong member" shows up,
    and hit@3 hides it.
2. **answer_correct** — LLM judge, binary, against the expected answer
3. **fabrication_rate** — on `out_of_scope` only: share of questions
   answered instead of escalated

Always report **per category**, not just aggregate.

## Model choices (deliberate — do not "upgrade" these)

- **Embeddings:** BGE-M3. Multilingual, and produces dense *and* sparse
  vectors from one model. Self-hosted.
- **Sparse:** BGE-M3 sparse output (or BM25 as a fallback).
- **Reranker:** BGE-reranker, self-hosted.
- **Generation:** Claude Haiku 4.5, temperature 0, held constant.
  Chosen *because* it is modest. A stronger model papers over bad
  retrieval and compresses the gap between configurations, which would
  destroy the experiment.
- **Judge:** Claude Opus 5. Must be a different model from the
  generator — models tend to favour their own output.
  **Temperature 0 is not achievable here**: Claude Opus 5 removed
  `temperature` (400 on any value). The judge runs with thinking
  disabled at `effort: "low"` and a schema-constrained verdict instead —
  the nearest available substitute. The generator, Haiku 4.5, does still
  accept `temperature` and runs at 0 as specified.

Document this reasoning in the README. It is a selling point, not a
footnote.

**Implementation note — these models come from FlagEmbedding, not
fastembed.** Checked against fastembed 0.8.0: it carries no `bge-m3` in
either `TextEmbedding` or `SparseTextEmbedding`, and its only BGE
reranker is `bge-reranker-base`, not `v2-m3`. Going through fastembed
would have substituted all three models at once and made the README's
stated rationale false. FlagEmbedding is the alternative this file
already named; it costs a large torch install and nothing else.

Do not "simplify" this back to fastembed without re-reading the
paragraph above — the substitution is not visible from the code.

## Chunking

One document = one chunk. Documents are written short enough for this
to be reasonable.

**The corpus holds deliberate confusable clusters** — groups of
near-identical documents differing mainly in their exact values (twelve
massages, eight facials, eight body treatments, six spa days, five
category-specific cancellation windows). That similarity is the
experiment, not an accident of writing. A new document must never
restate a value an existing document already owns.

**Do not optimise chunking.** It is a second variable and it is out of
scope. If a document is too long for one chunk, shorten the document.

## Stack

- Python 3.11+
- Qdrant, local, via `docker-compose.yml`
- `qdrant-client`, `fastembed` (or `FlagEmbedding`), `anthropic`,
  `python-dotenv`, `pandas`

`matplotlib` and `tabulate` are also in `requirements.txt` — for the
phase-4 score-distribution plot and the results table respectively.

**Verify library APIs against current documentation before using them.**
Do not trust remembered signatures — Qdrant's query API in particular
has changed across versions. Named vectors and server-side RRF fusion
are the relevant features here.

## Commands

```bash
cp .env.example .env          # then fill in ANTHROPIC_API_KEY
docker compose up -d          # Qdrant on :6333 (REST) / :6334 (gRPC)
pip install -r requirements.txt

curl http://localhost:6333/healthz          # Qdrant is up
curl http://localhost:6333/collections      # collection exists / point count
docker compose down                          # stop; storage survives in ./qdrant_storage
```

```bash
python src/validate_testset.py   # corpus <-> testset consistency; stdlib only
python src/ingest.py             # rebuild the collection from data/corpus/
python src/query_check.py        # manual retrieval check, 4 sample questions
python src/query_check.py "..."  # same, on an ad-hoc question

python src/build_oos_probe.py    # rebuild data/oos_probe.json from the test set
python src/oos_probe.py          # 20 out-of-scope questions x 3 configs
```

The probe measures fabrication on a denominator of 20 instead of 9, and
nothing else. It does not touch `data/testset.json` and produces no
retrieval metrics — every probe question has an empty `expected_doc_ids`.
Adding a question to it means adding its subject to the forbidden-topics
list in the phase 1 spec first.

Phase 5 — the serving demo. Not part of the benchmark; nothing here can
change a published number.

```bash
python src/escalation_eval.py    # escalation detector vs the judge, split by config
python src/test_routing.py       # both workflow branches, end to end (2 API calls)

uvicorn service:app --app-dir src --port 8000   # the endpoint n8n calls
cloudflared tunnel --url http://localhost:8000  # expose it to the remote n8n
```

`service.py` refuses to serve unless `RAG_SERVICE_SECRET` is set — the
tunnel URL is public. `n8n/support-workflow.json` is the workflow to import.

`ingest.py` drops and recreates the collection every time. That is
intentional — 18 documents are cheap to re-encode, and a rebuilt
collection is easier to trust than a patched one.

There is no test runner, linter, or CI in this repository. Do not invent
a command that has not been written; add the script first, then document
its exact invocation here.

## Current state

Phase status lives in `PLAN.md`. Update it there when a phase
completes, not here.

**Read `DECISIONS.md` before writing anything that describes a result.**
It holds decisions taken outside the repository — which are not
re-openable — and the reading reserves that bind every text produced
here, including how the fabrication metric must be phrased.

Two standing habits regardless of phase:

- Run `python src/validate_testset.py` after touching a corpus filename
  or the test set. It fails on a `doc_id` that no longer resolves — the
  failure mode this file warns about, which is otherwise silent.
- Read the **forbidden topics** list in
  `docs/superpowers/specs/2026-08-16-phase1-corpus-and-testset-design.md`
  before adding or editing a corpus document. Six subjects must stay
  uncovered; covering one turns an `out_of_scope` question into a
  mis-annotated one.

## Determinism

- `temperature=0` everywhere
- Pin the Qdrant image tag and library versions once the first run works
- Fixed question order
- Persist every raw run so results can be re-audited without re-running
  — see "Run artefacts" below

## Run artefacts

```
reports/
├── runs/   committed. One file per run referenced in RESULTS.md.
└── tmp/    gitignored. Everything else — debug runs, scratch.
```

The raw runs are the evidence for the numbers in the README. On a public
repository whose claim is "measured, not asserted", ignoring them means
nobody can check the results. Debug runs are excluded because they would
drown the signal, not because they are secret.

**Every file in `reports/runs/` must be self-describing.** Its header
carries:

- run id and timestamp
- git commit hash
- exact model identifiers: generation, judge, embedding, reranker
- retrieval config id (`dense` / `hybrid` / `hybrid_rerank`)
- `top_k`, `candidate_k`, and the threshold if one is set

A results file that cannot be tied back to the configuration that
produced it proves nothing. It is a number with a story attached, which
is what this project exists to avoid.

**Every row in `RESULTS.md` must cite the filename of its run
artefact.** This is what makes the chain auditable end to end: published
number → run file → the raw generated answer that produced it. A row
without a citation is an assertion.

## Security

- Never commit a real key. `.env` is gitignored; `.env.example` holds
  placeholders only.
- Never hardcode a key "just to test".
- This repository is public.

## Conventions

- **All committed content in English** — code, comments, corpus,
  documentation, commit messages.
- Corpus files: `data/corpus/<doc_id>.md`, where `doc_id` is stable and
  descriptive (`pricing_massage`, `cancellation_policy`).
- The `doc_id` is the ground truth key. If a corpus file is renamed,
  `data/testset.json` must be updated in the same commit — otherwise
  results silently become wrong.

## Build order

**The phases and their current status live in `PLAN.md`.** Read it
before starting work. It is not duplicated here — two copies of a plan
diverge, and the stale one is always the one being read.

Phases 1–4 are the benchmark and stand alone; 5–7 package it. If time
runs out at the end of phase 4, the work is still complete.

Do not skip ahead. Each phase ends with something testable.

The one point worth restating: phase 1 determines the validity of every
number produced later. A mis-annotated `expected_doc_ids` makes the
whole report lie, silently. Treat it as the most important phase, not
the warm-up.

## Out of scope

Chunking optimisation, embedding model comparison, reranker comparison,
a chat UI, streaming, conversation memory, production deployment.

The goal is a defensible measurement, not the best possible RAG system.

**This list scopes the benchmark — phases 1–4 in `PLAN.md`.** Phases 5–7
package the result and are deliberately outside it: an n8n workflow
demo, and a handover state machine holding a `conversation_state` per
conversation.

That state machine is not "conversation memory" in the sense banned
above. It stores routing state — is this thread being handled by the bot
or by a human — and no dialogue history. Nothing in it feeds the
retrieval or the generation, so it cannot vary a result. Do not extend
it into memory of what was said.

## Ask before

- Adding a dependency
- Changing anything in the "Model choices" section
- Changing the metric definitions
- Modifying `data/testset.json` after phase 3 has run
