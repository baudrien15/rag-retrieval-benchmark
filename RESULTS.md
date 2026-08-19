# Run log

One entry per run. Never overwrite an entry — append.
This file is the source for the README results section.

Every row cites the run artefact it came from, by filename, in
`reports/runs/`. A row without a citation is an assertion, not a
measurement, and the chain from published number down to the raw
generated answer is what this project is for.

**`hit@1` is the headline retrieval metric.** `hit@3` is still reported,
but it saturates at the top of the table — `hybrid_rerank` scores 100%
on the expanded corpus, so hit@3 can no longer separate the best
configuration from a better one. With clusters of near-identical
documents in the corpus, rank 1 is also where the failure that matters
shows up: retrieving the right cluster but the wrong member produces a
confidently wrong figure, and hit@3 counts that as a hit.

---

## Run 2026-08-18-2 — expanded corpus

**Config:** generation=`claude-haiku-4-5-20251001` (temperature 0)
judge=`claude-opus-5` (thinking disabled, effort low, schema-constrained)
embed=`BAAI/bge-m3` rerank=`BAAI/bge-reranker-v2-m3`
top_k=`3` candidate_k=`20` threshold=`none`
**Commit:** `173f594a19369f879bd4251dcc5fece9c17231b1`
**Corpus / test set:** 62 documents, 66 questions (30 exact_term,
15 semantic, 12 multi_fact, 9 out_of_scope)
**Changed since last run:** corpus 18 → 62 documents with deliberate
confusable clusters; test set 30 → 66 questions with the original 30
frozen; `hit@1` adopted; `hybrid_rerank` crash fixed.

### Headline

| Config | hit@1 | hit@3 | Answer correct | Fabrication (OOS, n=9) | Artefact |
|--------|-------|-------|----------------|------------------------|----------|
| dense | 88% | 95% | 83% | 0 / 9 | `runs/2026-08-18T093939Z-dense.json` |
| hybrid | 84% | 93% | 85% | 0 / 9 | `runs/2026-08-18T093939Z-hybrid.json` |
| **hybrid_rerank** | **91%** | **100%** | **89%** | 0 / 9 | `runs/2026-08-18T093939Z-hybrid_rerank.json` |

Fabrication is a count, not a rate: no fabrication observed on 9
out-of-scope questions per configuration, which bounds the true rate at
roughly 33% at worst (rule of three, 95% confidence interval).

### hit@1 per category

| Config | exact_term | semantic | multi_fact | Artefact |
|--------|-----------|----------|------------|----------|
| dense | 90% | 80% | 92% | `runs/2026-08-18T093939Z-dense.json` |
| hybrid | 90% | 87% | **67%** | `runs/2026-08-18T093939Z-hybrid.json` |
| hybrid_rerank | **97%** | 80% | 92% | `runs/2026-08-18T093939Z-hybrid_rerank.json` |

### hit@3 per category — saturated at the top

| Config | exact_term | semantic | multi_fact | Artefact |
|--------|-----------|----------|------------|----------|
| dense | 97% | 87% | 100% | `runs/2026-08-18T093939Z-dense.json` |
| hybrid | 90% | 93% | 100% | `runs/2026-08-18T093939Z-hybrid.json` |
| hybrid_rerank | 100% | 100% | 100% | `runs/2026-08-18T093939Z-hybrid_rerank.json` |

### Answer correct per category

| Config | exact_term | semantic | multi_fact | out_of_scope | Artefact |
|--------|-----------|----------|------------|--------------|----------|
| dense | 90% | 73% | 67% | 100% | `runs/2026-08-18T093939Z-dense.json` |
| hybrid | 83% | 93% | 67% | 100% | `runs/2026-08-18T093939Z-hybrid.json` |
| hybrid_rerank | 90% | 93% | 75% | 100% | `runs/2026-08-18T093939Z-hybrid_rerank.json` |

### Judge reliability for this run

98.5% self-agreement on `correct` (195/198 verdicts reproduced on
replay), 100% on `escalated` (198/198).
Artefact: `runs/2026-08-18-judge-stability-expanded.json`.
Full analysis: `docs/judge-reliability.md`.

**One flip per ~66 judgements is roughly one question per configuration.**
That sets the floor for what any difference below can mean.

### Observations

**Reranking is the only intervention that pays.** `hybrid_rerank` leads
or ties on every retrieval measure: 91% hit@1, 100% hit@3, 97% hit@1 on
`exact_term`. Its advantage over `hybrid` — 93% → 100% hit@3 — is the
signature of a reranker doing its job. It does not find different
documents; it reorders the same candidates. RRF fusion had already
retrieved the right document and was ranking it below a sibling.

**The project's central prediction is refuted.** CLAUDE.md predicts
dense-only retrieval underperforms on `exact_term`. Measured: **90%
hit@1 for both `dense` and `hybrid`.** Adding sparse retrieval bought
nothing on exact terms — even against twelve near-identical massage
documents with twelve different prices. The category is unlocked by
reranking (97%), not by lexical matching. This was the hypothesis the
whole corpus was rebuilt to test properly, and it did not survive.

**`hybrid` is the worst configuration for retrieval.** 84% hit@1,
below `dense`. The damage is localised: **`multi_fact` 67% against 92%
for `dense`.** Where an answer needs two documents, RRF promotes a
lexically similar sibling into rank 1 and displaces one of the pair.
This is a real cost of adding sparse retrieval, not noise — hit@1 does
not pass through the judge.

**`semantic` hit@1, raw counts:** `dense` 12 of 15, `hybrid` 13 of 15,
`hybrid_rerank` 12 of 15. The category holds 15 questions and the whole
spread is one question — smaller than the verdict movement observed
between the two judge passes. No ordering is read from it.

**Do not read the `dense` vs `hybrid` answer_correct gap.** 83% against
85% is ~1.3 questions against a ~1 question noise floor, and the ranking
inverts under a second judging pass (82% against 88%). `hybrid_rerank`
scores 89% under both passes.

**No fabrication was observed on 9 out-of-scope questions**, in any
configuration. The generation prompt holds — no configuration answered
an out-of-scope question. But 9 questions per config bound the true rate
at roughly 33% at worst (rule of three, 95% confidence interval): the
observation cannot be distinguished from a merely low rate.

### The q03 / q66 pair

Two questions asking the same thing, one naming the booking type and one
not. The pair separates *retrieval failed* from *the customer did not
specify*. Both are annotated to `cancellation_policy` (24 hours).

| | q03 "How many hours ahead do I need to cancel?" | q66 "…to cancel a single treatment?" | Artefact |
|---|---|---|---|
| dense | miss (rank > 3) | hit@3 (rank 2), **correct** | `runs/2026-08-18T093939Z-dense.json` |
| hybrid | miss (rank > 3) | **miss (rank > 3)** | `runs/2026-08-18T093939Z-hybrid.json` |
| hybrid_rerank | **hit@1 (rank 1)** | hit@3 (rank 3), **correct** | `runs/2026-08-18T093939Z-hybrid_rerank.json` |

**It did not come out as expected, in both directions.**

q03 was expected to miss across all configurations. `hybrid_rerank`
retrieved `cancellation_policy` at **rank 1** — the reranker resolved
the default-versus-override problem that both other configurations
failed. The unqualified question is harder, but it is not unretrievable.

q66 was expected to succeed everywhere. **`hybrid` misses it entirely**,
retrieving `cancellation_courses`, `cancellation_group_bookings` and
`cancellation_spa_days`. Naming "a single treatment" did not help it:
the word "treatment" appears throughout the cancellation cluster, so the
lexical signal that was supposed to disambiguate instead pulled in every
sibling.

**All three configurations score q03 as a wrong answer**, including the
one that retrieved the right document at rank 1. Its answer was:

> It depends on what you've booked: individual treatment 24 hours, spa
> day package 72 hours, treatment course 48 hours.

Every figure is correct and in the corpus. It is a *better* answer than
the reference, which gives only 24 hours. The judge marked it wrong for
"inventing" the 72 and 48 hour periods. See `docs/judge-reliability.md`.

So the pair says something sharper than intended: for the unqualified
question, **retrieval was not the bottleneck for the best configuration
— scoring was.**

### Caveat on the recorded commit

All three artefacts record `173f594…-dirty`. The working tree was clean
when the run started. The dirt is documentation written while the run
was in flight (`docs/saturation-and-expansion.md`,
`docs/judge-reliability.md`, `docs/testset-bias-check.md`) plus the run's
own untracked artefacts. **No code affecting retrieval or generation
changed during the run.** `git_commit()` was fixed afterwards to stop
counting the harness's own output as uncommitted work; the fix could not
apply to a process that had already imported the module.

---

## Probe 2026-08-19 — out-of-scope only, 20 questions

**Not a benchmark run.** It measures one metric, fabrication, on a larger
denominator. `hit@1` and `hit@3` are not computed: every question here
has an empty `expected_doc_ids`, so retrieval metrics are undefined by
construction. Nothing in the run above changes, and `data/testset.json`
is untouched.

**Why.** Nine out-of-scope questions with no fabrication bound the true
rate at roughly 33% by the rule of three — the weakest number in this
repository, and weak because of the denominator rather than the
observation. Twenty bound it at roughly 15%.

**Config:** as in run 2026-08-18-2 — same models, same parameters, same
imports, so a fabrication counted here means what it means above.
**Question set:** `data/oos_probe.json` — the 9 out-of-scope questions
copied from `data/testset.json` by `src/build_oos_probe.py`, plus 11 new
subjects, each checked to have zero occurrences across the 62 documents
and recorded in the forbidden-topics list.

| Config | Questions | Fabrications | frozen 9 | new 11 | Artefact |
|--------|-----------|--------------|----------|--------|----------|
| dense | 20 | **0 / 20** | 0 / 9 | 0 / 11 | `runs/2026-08-19T112932Z-dense-oos-probe.json` |
| hybrid | 20 | **0 / 20** | 0 / 9 | 0 / 11 | `runs/2026-08-19T112932Z-hybrid-oos-probe.json` |
| hybrid_rerank | 20 | **0 / 20** | 0 / 9 | 0 / 11 | `runs/2026-08-19T112932Z-hybrid_rerank-oos-probe.json` |

**No fabrication observed on 20 out-of-scope questions** per
configuration — 60 asked in total, not one answered instead of
escalated. The rule of three puts the 95% bound at roughly **15%**,
against 33% before. The generation prompt holds on subjects it has never
been tested against.

**Eleven subjects were drafted and rejected**, and the reason is the
result worth keeping. A question about a swimming pool or a tanning bed
looks out of scope, but `facilities` enumerates the facilities and calls
the sauna and hammam "our two heat facilities". An assistant answering
"there is no pool" from that enumeration is reasoning correctly and
would be counted as fabricating. The measurement would have been wrong
in the direction that flatters nobody — see the forbidden-topics section
of the phase 1 spec.

### Detector evidence, recorded in passing

Each answer also carries the verdict of `src/escalation.py`, used for
nothing here. Eleven of the twenty questions were new to it: **33
answers, 0 disagreements with the judge, 0/60 across the whole probe.**
All 60 answers are declinations, so this bears on missed escalations
only. See `docs/escalation-detector.md`.

---

## Run 2026-08-18-1 — original corpus (superseded: saturated)

**Config:** as above.
**Commit:** `3210c15333d0dc3f0d998f7db955540fdf9172eb` (`dense`);
`…-dirty` for the other two, from the `git_commit()` defect described
above.
**Corpus / test set:** 18 documents, 30 questions.

Kept because a result that turned out to be uninformative is still a
result. Full write-up: `docs/saturation-and-expansion.md`.

| Config | hit@3 | Answer correct | Fabrication (OOS, n=6) | Artefact |
|--------|-------|----------------|------------------------|----------|
| dense | **100%** | 97% | 0 / 6 | `runs/2026-08-18T083135Z-dense.json` |
| hybrid | 96% | 90% | 0 / 6 | `runs/2026-08-18T083135Z-hybrid.json` |
| hybrid_rerank | **100%** | 93% | 0 / 6 | `runs/2026-08-18T084052Z-hybrid_rerank.json` |

Per category (answer correct):

| Config | exact_term | semantic | multi_fact | out_of_scope | Artefact |
|--------|-----------|----------|------------|--------------|----------|
| dense | 100% | 100% | 83% | 100% | `runs/2026-08-18T083135Z-dense.json` |
| hybrid | 90% | 100% | 67% | 100% | `runs/2026-08-18T083135Z-hybrid.json` |
| hybrid_rerank | 90% | 100% | 83% | 100% | `runs/2026-08-18T084052Z-hybrid_rerank.json` |

`hit@1` is absent: the metric was adopted after this run.

**Observations.** The benchmark saturated. `dense` scored 100% hit@3 in
every category — across 90 questions asked there was exactly **one**
retrieval miss. Top-3 out of 18 documents retains a sixth of the corpus
per question, so no configuration could be distinguished from any other.
The ranking also came out backwards (`dense` ≥ `hybrid_rerank` >
`hybrid`), and every difference sat inside the judge's measured
disagreement rate.

Judge reliability for this run: 98.9% on `correct` (89/90), 100% on
`escalated`. Artefact:
`runs/2026-08-18-judge-stability-pre-expansion.json`.
