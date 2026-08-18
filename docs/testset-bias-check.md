# Test set bias check — lexical overlap between questions and their documents

**Date:** 2026-08-18
**Applies to:** `data/testset.json` at 66 questions, corpus at 62 documents
**Script:** `python src/lexical_overlap.py` (stdlib only, `--verbose` for
every question)
**Raw output:** `reports/tmp/lexical_overlap.json`

Recorded whether or not it found a problem. A check that passes is worth
writing down precisely because it passed — otherwise the next reader has
no way to tell a check that was run from a check that was assumed.

---

## Hypothesis

The 36 questions added with the corpus expansion were written **while
reading their source documents**. The original 30 were written before
those documents existed.

Writing a question with the document open imports its vocabulary: exact
treatment names, exact phrasing, exact numbers. **Verbatim lexical match
is precisely what sparse retrieval catches and dense retrieval misses.**

So the added questions plausibly favour `hybrid` and `hybrid_rerank`
over `dense` for a reason that has nothing to do with retrieval quality
— and in the *same direction* as the conclusion this benchmark expects
to reach. A confound aligned with the expected result is the most
dangerous kind, because nothing about the outcome will look wrong.

**Hypothesis to test:** the added questions show materially higher
verbatim overlap with their expected documents than the original ones.

---

## Method

For each question with at least one expected document:

1. Lowercase, tokenise on `[a-z0-9]+`.
2. Drop function words against a short explicit stop list — 80 entries,
   written into the script rather than pulled from a library, so the
   measure is reproducible without a dependency. Function words carry no
   retrieval signal and counting them would drag every score towards a
   meaningless middle.
3. Build the vocabulary of the expected documents the same way (the
   union, where a question has two).
4. **Overlap = share of the question's content words that appear
   verbatim in that vocabulary.** No stemming, no lemmatisation: an
   exact-match measure, because exact match is the mechanism under
   suspicion.

`out_of_scope` questions have no expected document and are excluded — 9
of the 66. That leaves 57 measured: 24 original, 33 added.

**Grouping.** `original` is q01–q30, `added` is q31 onwards. This is the
line that matters, because it is the line between "written before the
document" and "written with the document open".

---

## Result 1 — first measurement, before any change

| Group | n | mean | median | min | p25 | p75 | max |
|---|---|---|---|---|---|---|---|
| original (q01–q30) | 24 | 64% | 67% | 20% | 43% | 96% | 100% |
| added (q31–q65) | 32 | **79%** | 80% | 17% | 72% | 100% | 100% |

**Gap in means: +15.0 points.** The hypothesis is confirmed at the
aggregate level.

The `p25` column is the sharper signal. A quarter of the original
questions sit below 43% overlap — genuinely paraphrased questions that
share almost no wording with their source. The added set's lower quarter
only reaches down to 72%. The added set had **no real paraphrase tail**.

### The gap is not uniform

| Category | original | added | difference |
|---|---|---|---|
| `exact_term` | 88% | 89% | +1 |
| `semantic` | 39% (med 42%) | 48% (med 43%) | +9 mean, +1 median |
| `multi_fact` | 59% | **83%** | **+24** |

Two distinct effects were stacked:

1. **A category-mix artefact.** 59% of the added questions are
   `exact_term`, against 42% of the originals. That category
   legitimately carries very high overlap — naming a treatment and
   asking its price *is* what an `exact_term` question is. Adding
   proportionally more of them raises the aggregate without any single
   question being badly written.
2. **A genuine confound in `multi_fact`**, +24 points. Not a mix effect.
   These questions named treatments and membership tiers exactly as the
   documents spell them, and that was my doing.

The aggregate figure alone would have prompted the wrong fix — rewriting
everything, including the `exact_term` questions that showed no bias at
all.

---

## What changed

**The six added `multi_fact` questions were rewritten in customer
voice**: the treatment described rather than named, the way someone who
has never seen the price list would ask.

| Q | Before | After |
|---|---|---|
| q57 | "What does the 60-minute Swedish Classic Massage come to on a Sunday?" | "How much would the classic full-body massage, an hour of it, cost me on a Sunday all in?" |
| q58 | "I'm on the Radiance membership. Can I use my monthly treatment on the Clay Cocoon Ritual?" | "I pay for the dearer of the two monthly plans. Does that cover the clay wrap ritual?" |
| q59 | "We booked the whole spa privately and need to cancel a week before. What do we lose?" | "We hired the whole place for a party and now have to call it off with a week to go. What do we lose?" |
| q60 | "Does the evening supplement apply to the Express Chair Massage, and how much is it?" | "Is there a surcharge on the quick seated massage if I come in late afternoon or evening, and how much?" |
| q61 | "I have the Serenity membership. Can my monthly treatment be the Herbal Poultice Massage?" | "I'm on the cheaper monthly plan. Could this month's treatment be the one with the steamed herb bundles?" |
| q62 | "Can my guide dog stay with me during the Mineral Mud Wrap?" | "I'm blind and travel with a dog. Can she stay in the room while I have the mud treatment?" |

`expected_doc_ids` and `expected_answer` were **not touched**. Phrasing
only, exactly as scoped.

### What was deliberately left alone

**`exact_term`, at 88% against the originals' 88%.** It shows no bias
whatsoever. Rewriting it would have made the added `exact_term`
questions *easier* for dense retrieval than their original
counterparts — introducing the mirror-image confound in order to fix one
that was not there. The temptation to "clean up" the whole set is the
wrong instinct here.

**`semantic`, at 48% against 39%.** The means differ by 9 points but the
medians are 43% against 42%. The mean gap comes from a small number of
short questions where nearly every content word is unavoidable — "Can I
bring my dog?" scores 100% because `pets_policy` necessarily contains
both "bring" and "dog", and there is no natural way for a customer to
ask it otherwise. Rewriting to force the number down would produce
questions no customer would type.

---

## Result 2 — after the rewrite

| Category | original | added |
|---|---|---|
| `exact_term` | 88% | 88% |
| `semantic` | 39% (med 42%) | 48% (med 43%) |
| `multi_fact` | 59% | **53%** |

| Group | n | mean | median | p25 | p75 |
|---|---|---|---|---|---|
| original | 24 | 64.1% | 66.7% | 43% | 96% |
| added | 33 | 72.9% | 75.0% | 53% | 100% |

`multi_fact` has gone from +24 points above the originals to 6 points
below them. The raw gap in means falls from **+15.0 to +8.9 points**.

### Standardising for the category mix

The remaining +8.9 is dominated by composition, not phrasing. Applying
the original set's category mix (42% `exact_term`, 33% `semantic`, 25%
`multi_fact`) to both groups' per-category means:

| | standardised mean |
|---|---|
| original | 64.1% |
| added | 65.7% |
| **residual gap** | **+1.7 points** |

---

## Conclusion

The hypothesis was correct and the confound was real: **+24 points on
`multi_fact`**, in the direction that would have inflated the headline
result. It has been removed by rewriting six questions.

**The residual is +1.7 points and is not zero.** It should not be
described as eliminated. It is small enough that it cannot plausibly
account for a difference between retrieval configurations — those are
measured in whole questions, and 1.7 points of vocabulary overlap across
57 questions is not a mechanism that moves a retrieval ranking.

**Limitations of this check.** It measures verbatim token overlap and
nothing else. It would not catch a question that shares no words with
its document but was still written to be findable — structural leakage
rather than lexical. Nor does it establish that overlap *causes* a
retrieval advantage; it establishes that the two groups are now
comparable on the axis where they demonstrably differed.

Rerun with `python src/lexical_overlap.py` against any future change to
the test set. The figures above are reproducible, not asserted.
