# PLAN.md — Build order

Seven phases. Each ends with something testable. Do not skip ahead.

Phases 1–4 produce the benchmark itself and stand on their own.
Phases 5–7 package it.

Status is maintained in this file. CLAUDE.md points here rather than
repeating the phases.

---

## Phase 0 — Domain

**Status: done.**

**Lumen Spa & Wellness**, a fictional wellness centre offering treatments
by appointment.

Chosen because the domain is dense in exact terms — prices, treatment
names, durations, cancellation windows — which is where dense-only
retrieval is expected to fail. Deliberately not a hotel or a restaurant.

All content invented. No real business is modelled.

**Done when:** the domain is written down in one paragraph.

---

## Phase 1 — Corpus and test set

**Status: done.**

The phase that determines whether every later number means anything.

**Corpus:** 15–20 short documents in `data/corpus/<doc_id>.md`.
FAQ, price list, treatment descriptions, cancellation policy, opening
hours, gift cards. Each `doc_id` is stable and descriptive — it is the
ground truth key.

**Test set:** 30 questions in `data/testset.json`, phrased the way a
customer would actually write, split across four categories:

| Category | Count | Purpose |
|----------|-------|---------|
| `exact_term` | ~10 | Prices, names, durations |
| `semantic` | ~8 | Paraphrase, indirect phrasing |
| `multi_fact` | ~6 | Requires two documents |
| `out_of_scope` | ~6 | No correct document; correct behaviour is escalation |

Each entry carries `expected_doc_ids`, `expected_behavior` and a short
`expected_answer` for the judge.

**Done when:** 30 annotated questions, every `expected_doc_id` resolving
to a file that actually exists.

**Delivered.** 18 documents, 171–241 words each. 30 questions, split
10 / 8 / 6 / 6, fixed order `q01`–`q30`. Verified by
`python src/validate_testset.py`, which fails on any `doc_id` that no
longer resolves. Design record and the six forbidden out-of-scope
subjects:
`docs/superpowers/specs/2026-08-16-phase1-corpus-and-testset-design.md`.

---

## Phase 2 — Qdrant

**Status: done.**

One collection with **named vectors**: one dense, one sparse.
One document = one chunk. Chunking is not a variable here.

Instance runs locally via `docker-compose.yml`. Nothing leaves the
machine.

**Done when:** a manual query returns sensible results.

**Delivered.** Collection `lumen_spa` on Qdrant v1.19.0 (image tag now
pinned): named vector `dense` (1024d, cosine) and named sparse vector
`sparse`, 18 points, every `doc_id` confirmed retrievable from its
payload after the round trip. `python src/ingest.py` rebuilds it from
scratch; `python src/query_check.py` is the manual check.

Embeddings go through **FlagEmbedding**, not fastembed — fastembed 0.8.0
carries no `bge-m3` in either embedding class and only
`bge-reranker-base`. See the implementation note in CLAUDE.md.

RRF fusion is done server-side by Qdrant rather than reimplemented.

Two observations from the sanity check, to be measured properly in
phase 3 rather than trusted from four questions:

- The out-of-scope question scores visibly lower on dense (0.41) than
  the in-scope ones (0.56–0.66). Encouraging for the phase 4 threshold.
- q23 retrieves `facilities` but not `contraindications` in any
  configuration. Not an indexing fault — `contraindications` ranks first
  for "after surgery, how long before a heat treatment". The word
  "sauna" simply dominates the query. This is the kind of multi-document
  failure the category exists to expose.

---

## Phase 3 — Harness

**Status: done.** Run 2026-08-18-2, all three configurations, 66 questions. Results in `RESULTS.md`.

Python, not n8n — this needs repeatability and metrics.

Runs all 30 questions across three configurations:

| ID | Retrieval |
|----|-----------|
| `dense` | Dense only |
| `hybrid` | Dense + sparse, RRF fusion |
| `hybrid_rerank` | Dense + sparse + reranking |

Three metrics: `hit@3`, judged answer correctness, and fabrication rate
on out-of-scope questions. Reported **per category**, not only aggregate.

Every raw run persisted to `reports/runs/`, self-describing, and cited by
filename from the `RESULTS.md` row it produced. Scratch and debug runs go
to `reports/tmp/`, which is gitignored.

**Done when:** the results table exists in `RESULTS.md`.

`data/testset.json` freezes once this phase has run — changing it
afterwards breaks comparison with earlier runs. Ask first.

**Built.** `src/generation.py` (generator + judge, both prompts frozen as
module constants) and `src/harness.py`. Run with
`python src/harness.py`; `--tmp` writes to the gitignored scratch
directory instead.

**One specified thing could not be built as written.** CLAUDE.md asks for
the judge at temperature 0. **Claude Opus 5 rejects `temperature`** — the
parameter was removed on Opus 4.7 and later and returns a 400. The judge
instead runs with thinking disabled at `effort: "low"` and a
schema-constrained verdict, which is the nearest the model offers. The
actual parameters sent are recorded verbatim in every run artefact, so a
reader sees what ran rather than what was intended.

---

## Phase 4 — Confidence threshold

**Status: done — and the answer was "no threshold".**

No fabrication was observed on 9 out-of-scope questions in any of the
three configurations — a rate bounded at roughly 33% at worst (rule of
three, 95% confidence interval) — so there is nothing for a threshold to
remove; it could only cost correct answers.
`SCORE_THRESHOLD` stays unset. The distributions were plotted anyway,
and the transferable finding is that a cross-encoder score separates
in-scope from out-of-scope cleanly (100% caught for 12% lost) while an
RRF score does not (44% for 12%), because an RRF score is a rank fusion
artefact rather than a similarity. See `docs/threshold-analysis.md`.

Plot retrieval score distributions, in-scope against out-of-scope. If
they separate cleanly the cutoff reads off the chart.

Then measure what the threshold costs and buys: fabrications removed
against correct answers lost. The trade-off is the finding, not the
threshold itself.

**Done when:** a justified cutoff plus before/after numbers.

**Follow-up, 2026-08-19: the denominator was the weak part, so it was
enlarged.** A separate 20-question out-of-scope probe
(`data/oos_probe.json`, `src/oos_probe.py`) returned no fabrication on
20 questions per configuration, tightening the rule-of-three bound from
roughly 33% to roughly 15%. `data/testset.json` stays frozen and no
other metric moves: folding the questions into the test set would have
taken `out_of_scope` from 14% to 26% of it, inflating every aggregate in
the category where all three configurations already score 100%.

---

## Phase 5 — Workflow demo

**Status: in progress.** Detector, service and canvas built and tested
locally. Not yet imported into the remote n8n instance, so the "readable
on screen" criterion is not met.

An n8n workflow making the pipeline legible at a glance:
inbound webhook → conversation state check → hybrid retrieval →
generated answer or escalation.

A simulated webhook call is sufficient. No telephony provider needed.

**Done when:** the canvas is readable on screen.

**The threshold test node was dropped.** Phase 4 measured that no
threshold is worth adopting, so a gate node would demonstrate a
component the benchmark rejected. It survives on the canvas as a sticky
note carrying the measured cost — decision 6 in `DECISIONS.md`.

**Escalation routing does not come from the generator.** The judge's
`escalated` field needs a reference answer and does not exist at serving
time, and making the generator emit a structured field would have
changed `GENERATION_SYSTEM`, the constant held identical across the
three runs. Instead a pure function reads the generated answer:
`src/escalation.py`, written on the `dense` artefacts and measured on
the `hybrid` and `hybrid_rerank` artefacts — 1 missed escalation of 37
rows, 0 wrong escalations of 155. **The split is by configuration, not
by question**: all 66 questions appear in both sets, so the genuinely
unseen evidence is **3 of 4 answers**. Reported at that strength in
`docs/escalation-detector.md`, which also records why a question-level
split is the better design for a rerun.

**Delivered so far.**

- `src/escalation.py` — the detector, pure, no model call
- `src/escalation_eval.py` — the measurement and its split caveat, artefact in
  `reports/runs/`
- `src/service.py` — FastAPI front end, shared-secret header, imports
  `retrieval.py` and `generation.py` unchanged
- `src/test_routing.py` — both branches end to end, passing 4/4
- `n8n/support-workflow.json` — the canvas
- `docs/escalation-detector.md` — the rule, the split, both rates, the
  single disagreement

**Still to do.** Import the workflow on the VPS, run it through a
cloudflared tunnel, and add the conversation state check that phase 6
defines.

---

## Phase 6 — Handover state machine

**Status: not started.**

A `conversation_state` table: conversation id, state
(`bot` / `human` / `paused`), last human activity timestamp.

State is read in the first node of the inbound workflow and the workflow
exits immediately if the state is `human`. An agent replying flips the
state. After an idle period it returns to `bot` automatically.

**Done when:** the bot answers, then goes silent after a human writes in
the same thread, then resumes.

---

## Phase 7 — Packaging

**Status: not started.**

- `README.md` filled in with real numbers, including the limitations section
- A short screen recording: results table first, then the workflow, then
  an out-of-scope question triggering escalation, then the handover
- Library versions and the Qdrant image tag pinned

**Done when:** someone can read the README and know what was measured,
how, and what it does not prove.

---

## Stopping point

Phases 1–4 are the benchmark. If time runs out there, the work still
stands — the results table and the calibrated threshold carry the
substance.

The real risk in this plan is not running out of time. It is drifting
into chunking optimisation, embedding comparisons and reranker
shootouts. This is not an attempt to build the best possible RAG system.
It is a measured demonstration of where the failures actually are.
