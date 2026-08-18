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

| Config | hit@1 | hit@3 | Answer correct | Fabrication (OOS) | Artefact |
|--------|-------|-------|----------------|-------------------|----------|
| dense | 88% | 95% | 83% | 0% | `runs/2026-08-18T093939Z-dense.json` |
| hybrid | 84% | 93% | 85% | 0% | `runs/2026-08-18T093939Z-hybrid.json` |
| **hybrid_rerank** | **91%** | **100%** | **89%** | 0% | `runs/2026-08-18T093939Z-hybrid_rerank.json` |

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

**`hybrid` leads on `semantic`** (87% vs 80% hit@1), the category where
the plan predicted it would add nothing. One question out of 15. Not
defended as a result.

**Do not read the `dense` vs `hybrid` answer_correct gap.** 83% against
85% is ~1.3 questions against a ~1 question noise floor, and the ranking
inverts under a second judging pass (82% against 88%). `hybrid_rerank`
scores 89% under both passes.

**Fabrication is 0% everywhere.** The generation prompt holds — no
configuration answered an out-of-scope question. But 9 questions per
config cannot distinguish 0% from merely low.

### The q03 / q66 pair

Two questions asking the same thing, one naming the booking type and one
not. The pair separates *retrieval failed* from *the customer did not
specify*. Both are annotated to `cancellation_policy` (24 hours).

| | q03 "How many hours ahead do I need to cancel?" | q66 "…to cancel a single treatment?" |
|---|---|---|
| dense | miss (rank > 3) | hit@3 (rank 2), **correct** |
| hybrid | miss (rank > 3) | **miss (rank > 3)** |
| hybrid_rerank | **hit@1 (rank 1)** | hit@3 (rank 3), **correct** |

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

## Run 2026-08-18-1 — original corpus (superseded: saturated)

**Config:** as above.
**Commit:** `3210c15333d0dc3f0d998f7db955540fdf9172eb` (`dense`);
`…-dirty` for the other two, from the `git_commit()` defect described
above.
**Corpus / test set:** 18 documents, 30 questions.

Kept because a result that turned out to be uninformative is still a
result. Full write-up: `docs/saturation-and-expansion.md`.

| Config | hit@3 | Answer correct | Fabrication (OOS) | Artefact |
|--------|-------|----------------|-------------------|----------|
| dense | **100%** | 97% | 0% | `runs/2026-08-18T083135Z-dense.json` |
| hybrid | 96% | 90% | 0% | `runs/2026-08-18T083135Z-hybrid.json` |
| hybrid_rerank | **100%** | 93% | 0% | `runs/2026-08-18T084052Z-hybrid_rerank.json` |

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
