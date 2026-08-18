# The benchmark saturated, and what was done about it

**Date:** 2026-08-18
**Status:** the result below is superseded. It is kept because a result
that turned out to be uninformative is still a result, and because the
reason it was uninformative is the most transferable thing this project
has produced so far.

**Artefacts:** `reports/runs/2026-08-18T083135Z-dense.json`,
`…-hybrid.json`, `reports/runs/2026-08-18T084052Z-hybrid_rerank.json`

---

## What was measured

The first complete run of the benchmark: 30 questions across three
retrieval configurations, on the original 18-document corpus, at
`top_k=3`.

### hit@3 — pure retrieval

| Config | exact_term | semantic | multi_fact | Overall |
|---|---|---|---|---|
| `dense` | 100% | 100% | 100% | **100%** |
| `hybrid` | 100% | 88% | 100% | 96% |
| `hybrid_rerank` | 100% | 100% | 100% | **100%** |

### answer_correct, and fabrication on out_of_scope

| Config | exact_term | semantic | multi_fact | out_of_scope | Fabrication (n=6) |
|---|---|---|---|---|---|
| `dense` | 100% | 100% | 83% | 100% | 0 / 6 |
| `hybrid` | 90% | 100% | 67% | 100% | 0 / 6 |
| `hybrid_rerank` | 90% | 100% | 83% | 100% | 0 / 6 |

**Across 90 questions asked, there was exactly one retrieval miss** —
q14 under `hybrid`. Every other difference in the tables above comes
from generation or from the judge, not from retrieval. Retrieval is the
isolated variable; it is the only thing that was supposed to move.

---

## Why the result was inevitable

**Top-3 out of 18 documents.** Each question retains one sixth of the
corpus. A retriever does not have to rank well to score; it only has to
avoid ranking the correct document below fifteen others. There is no
headroom for any method to be distinguished from any other.

Three consequences, all visible above:

1. **The central prediction was not tested.** CLAUDE.md predicts that
   dense-only retrieval underperforms on `exact_term` questions. The
   measurement is 100% against 100% against 100%. That is not a
   refutation — it is a null result from an instrument with no
   resolution.
2. **The ranking came out backwards.** `dense` ≥ `hybrid_rerank` >
   `hybrid`. Taken at face value this says adding sparse retrieval hurts.
3. **The differences were inside the noise.** Judge self-agreement was
   measured at 98.9% — roughly one verdict flip per 90 judgements. The
   `exact_term` gap of 90% against 100% is one question out of ten. It
   is at the noise floor and means nothing. See
   `docs/judge-reliability.md`.

Point 3 only became visible because the judge was measured. Before that,
a 10-point category difference looked like a finding.

---

## Why "make the corpus bigger" was the wrong diagnosis

The first instinct was corpus size: 18 documents is small, so grow it to
60–80 and the ranking task becomes hard enough to discriminate.

**That diagnosis was wrong, and it would have produced the same result
at greater cost.** The binding constraint was never the number of
documents. It was that **every question mapped to a semantically unique
document**.

Ask "how much is the hot stone massage?" against a corpus holding one
document about massage pricing, one about facial pricing, one about
opening hours, and fifteen other clearly distinct subjects, and dense
embedding similarity is sufficient. Adding sixty more equally distinct
documents — parking, staff biographies, a history of the building —
leaves that property untouched. Dense retrieval would still score near
100%, on a corpus four times the size.

**The right diagnosis is confusability.** Dense retrieval fails when
several documents are *semantically near-identical* and differ mainly in
their exact values. That is not a contrived edge case; it is what a real
booking system looks like. Six massages described in near-interchangeable
prose with six different prices and durations. Several treatment tiers.
Cancellation windows that differ by service category.

The distinction matters because it changes what to build. Size is a
number to hit. Confusability is a structure to design.

*Credit where due: the size-versus-confusability correction came from
the repository owner, not from me. I had proposed the size fix.*

---

## What the expansion changed

Corpus 18 → 62 documents, built around deliberate confusable clusters:

| Cluster | Docs | What varies between members |
|---|---|---|
| Massage treatment sheets | 12 | €30–€150, 20–80 minutes, pressure, oil |
| Facial treatments | 8 | €45–€135, 30–90 minutes, skin type |
| Body rituals and scrubs | 8 | €40–€98, time spent wrapped |
| Spa day packages | 6 | €98–€340, hours, what is included |
| Cancellation by booking type | 5 | 48h / 72h / 5d / 7d / 14d notice |
| Single-topic practical documents | 5 | not a cluster; ordinary breadth |

Cluster members share most of their prose by construction. Finding the
right cluster but the wrong member now yields a confidently wrong
figure, which is the failure this benchmark exists to count.

Test set 30 → 66 questions. **The original 30 are frozen** — no wording,
no `expected_doc_ids`, no `expected_answer` changed. See
`docs/annotation-review-expansion.md` for the question-by-question
review, including the one `out_of_scope` question the expansion nearly
inverted.

**`hit@1` adopted alongside `hit@3`.** Once the corpus holds clusters,
rank 1 is where "right cluster, wrong member" shows up. hit@3 hides it —
retrieving the correct document at rank 3 behind two near-identical
siblings counts as a hit while being exactly the situation that produces
a wrong answer.

### Early evidence that it worked

Before any new run, retrieval ranks against the expanded corpus already
show the intended behaviour:

- **q01** — "How much is the hot stone massage?" The document holding
  the answer now ranks **4th**, behind `massage_himalayan_salt_stone`
  (75 min, €102) and `massage_herbal_poultice` (80 min, €118). Same
  cluster, wrong member, plausible wrong number.
- **q03** — "How many hours ahead do I need to cancel?" The annotated
  document does not appear in the top 5 at all. All five slots are taken
  by the category-specific cancellation cluster.

---

## Two defects found and fixed along the way

Neither affected a measurement, and both were the kind that produce
false confidence rather than visible failure.

1. **`hybrid_rerank` crashed on every pair.** FlagEmbedding's
   `FlagReranker` calls the slow tokenizer's `prepare_for_model`, which
   transformers 5 removed. The same model is now loaded through
   `AutoModelForSequenceClassification`. The model is unchanged.
2. **`print_table` cited `runs/` in hardcoded text.** A `--tmp` run
   printed a citation to a path where the file did not exist — a
   ready-made false citation for `RESULTS.md`, in a project whose stated
   claim is that every published number can be traced to its artefact.

A third was found while writing this document: **`git_commit()` marked
every configuration after the first as `-dirty`**, because the harness's
own artefacts are untracked files at the moment the next configuration
reads `git status`. The three artefacts above show it: `dense` carries a
clean SHA, `hybrid` and `hybrid_rerank` carry `-dirty` despite nothing
having changed between them. Fixed by ignoring untracked paths under
`reports/` when deciding dirtiness.

---

## What this episode is worth keeping

A benchmark can return a full set of plausible numbers while measuring
nothing. The tables at the top of this document are not wrong — they are
what the instrument reported. They are simply uninformative, and nothing
in their appearance says so. Had they been published as-is, they would
have read as "retrieval method barely matters", with three decimal-free
percentages to back it up.

Two properties made the emptiness visible:

- **Reporting per category rather than in aggregate.** A single overall
  figure of 97% would have looked like a decent result. The per-category
  table showing 100% everywhere is what exposed the ceiling.
- **Measuring the judge.** Without the 98.9% self-agreement figure,
  a 10-point category difference reads as a finding rather than as one
  question's worth of noise.
