# Annotation review — corpus expansion, 18 → 62 documents

**Date:** 2026-08-18
**Change under review:** 44 new corpus documents, 35 new questions,
`hit@1` added as a metric.
**Reviewer:** performed by Claude, for review by the repository owner.

The expansion was made because the benchmark had saturated: `dense`
scored 100% hit@3 across all 30 questions, so no configuration could be
distinguished from any other. The cause was confusability, not corpus
size — every question mapped to a semantically unique document. The
episode is written up in
[`saturation-and-expansion.md`](saturation-and-expansion.md), with the
original saturated tables.

This document records what the expansion did to the **original thirty
questions**, which are the ones that could silently break.

---

## Summary

| | Count |
|---|---|
| Original questions whose `expected_doc_ids` changed | **0** |
| Original questions whose `expected_answer` changed | **0** |
| Original questions whose wording changed | **0** |
| Original questions now **ambiguous** | **1** (q03) |
| `out_of_scope` questions **no longer out of scope** | **0** |
| Corpus documents edited during review to protect an annotation | **3** |

No annotation was rewritten. Where the expansion created a problem, the
**new document** was changed rather than the annotation — an annotation
edited to fit a corpus is an annotation that no longer tests anything.

---

## 1. Documents changed during the review

These three edits were made *after* the first draft of the new corpus,
because reading the drafts against the existing questions found
collisions. Each is a change to a new document, not to an original one.

### 1.1 `massage_aroma_candle.md` — protected q30

**q30 is `out_of_scope`:** *"Do you sell the oils you use in the
treatments?"* Correct behaviour is escalation.

- **Before:** "The remaining candle is not taken home — it stays with
  the treatment room and is used until it is finished."
- **After:** "The candle is lit fifteen minutes before the appointment
  so the oil is at temperature when you arrive, which is why this
  treatment cannot be started earlier than booked."

**Why.** The original sentence answers q30 in the negative. An assistant
retrieving it would correctly say the product is not taken away — and
would be scored as a **fabrication**, because it answered instead of
escalating. This is the inversion category: a right answer counted as a
wrong one.

### 1.2 `cancellation_private_hire.md` — removed a duplicated fact

- **Before:** "the 50% booking payment, which is not returned"
- **After:** "the booking payment already made, which is not returned"

**Why.** `groups_and_events` already owns the 50% private-hire booking
payment. The corpus rule is that each fact lives in exactly one
document; restating the figure would have given q24's multi-document
answer a single-document shortcut.

### 1.3 `cancellation_private_hire.md` — separated two notice periods

- **Added:** "This is the notice to cancel a booking that already
  exists. The separate and longer notice needed to make a private hire
  booking in the first place is set out with the private hire terms, not
  here."

**Why.** q24's expected answer states that private hire needs **three
weeks' notice** — that is notice *to book*, held by `groups_and_events`.
The new document sets **14 days** notice *to cancel*. Both are true and
they are different quantities. Without the added sentence the corpus
reads as self-contradictory, and a judge grading q24 would have had
grounds either way.

---

## 2. The one ambiguous question: q03

**q03 (`exact_term`):** *"How many hours ahead do I need to cancel?"*
**Annotated:** `cancellation_policy` → *"At least 24 hours before the
appointment. Cancelling less than 24 hours ahead is charged at 50% of
the treatment price."*

**Status: ambiguous. Annotation left unchanged. Your call.**

The expansion added five cancellation documents with five different
notice periods:

| Document | Notice | Applies to |
|---|---|---|
| `cancellation_policy` (original) | **24 hours** | an ordinary individual treatment |
| `cancellation_courses` | 48 hours | one session of a prepaid course |
| `cancellation_spa_days` | 72 hours | a spa day package |
| `cancellation_workshops` | 5 days | a workshop place |
| `cancellation_group_bookings` | 7 days | a group of four or more |
| `cancellation_private_hire` | 14 days | exclusive use of the spa |

The question names no booking type, so the default — an ordinary
treatment — is the right reading, and 24 hours remains the right answer.
Each new document also states in its opening line that it replaces the
standard terms *for that booking type only* and that an ordinary
treatment follows the standard terms instead. So the corpus does resolve
it.

**But the retrieval evidence is stark.** Against the expanded corpus,
`cancellation_policy` does not appear in the top 5 at all:

```
q03 top-5 (hybrid): cancellation_spa_days, cancellation_group_bookings,
                    cancellation_workshops, cancellation_private_hire,
                    cancellation_courses
```

All five slots are taken by the cluster. The annotated document is
unreachable at `top_k=3`, so q03 will score as a retrieval miss for
every configuration that cannot find it.

**Two readings, and they lead to different actions:**

1. *This is the benchmark working.* A question whose answer depends on a
   default, in a corpus full of near-identical overrides, is exactly the
   real-world failure this expansion was built to expose. Leave it.
2. *This is a broken question.* A customer asking it deserves "it
   depends on what you booked", and the annotation demands a single
   number. Then q03 should be reworded — which you have ruled out for
   the original thirty — or dropped from scoring.

**Decided: reading 1.** q03 stays exactly as annotated — not
disambiguated, not dropped. A retrieval miss across all three
configurations is an honest result and belongs in the README as a
failure mode retrieval cannot fix. A sibling question was added beside
it rather than altering it; see §8.

---

## 3. `out_of_scope` questions — checked explicitly

This is the category that silently inverts a result: a document that
answers the question turns a correct escalation into a counted
fabrication. Each of the six was checked by reading every new document
that retrieval surfaced for it, not by assuming.

| Q | Question | Still out of scope? | Evidence |
|---|---|---|---|
| q25 | Do you offer laser hair removal? | **Yes** | No new document mentions hair removal. `facial_mens_essential` mentions *ingrown hairs* after shaving — adjacent, but it does not offer or decline hair removal. |
| q26 | Will my health insurance reimburse the massage? | **Yes** | No new document mentions insurance, reimbursement or mutuelle. The cancellation cluster discusses refunds of payments made to us, which is a different subject. |
| q27 | Do you have a branch in Bordeaux? | **Yes** | No new document claims or denies a second site. `accessibility` describes one building; `spa_day_half_morning` names the same quay entrance. |
| q28 | Can you invoice my employer directly? | **Yes** | No new document mentions invoicing, purchase orders or B2B billing. `cancellation_private_hire` discusses payments already made by the customer. |
| q29 | My lower back has been hurting for three weeks. What's causing it? | **Yes** | No new document explains the cause of a symptom. Several massage documents describe firm pressure, which invites a recommendation — but recommending is not diagnosing, and this pressure already existed via `treatments_massage`. |
| q30 | Do you sell the oils you use in the treatments? | **Yes — after the fix in §1.1** | Before the fix, `massage_aroma_candle` answered it. After it, no document states whether any product can be bought or taken away. |

**Conclusion: none of the six was inverted.** One would have been, and
was caught by reading rather than by any automated check — the validator
cannot detect it, because a document answering an out-of-scope question
contains no forbidden term.

---

## 4. All thirty original questions

`Rank` is the position of the first annotated document in the top 5
under `hybrid` retrieval against the expanded corpus. It measures
difficulty, not correctness — a rank of 4 means the annotation is fine
and the question got harder, which is the point of the expansion.

| Q | Category | Annotation | Rank | New documents in top 5 |
|---|---|---|---|---|
| q01 | exact_term | unchanged | 4 | massage_himalayan_salt_stone, massage_herbal_poultice |
| q02 | exact_term | unchanged | 1 | spa_day_sunday, facial_age_focus |
| q03 | exact_term | unchanged — **ambiguous, §2** | **not in top 5** | the whole cancellation cluster |
| q04 | exact_term | unchanged | 1 | body_honey_wrap, body_algae_detox_wrap, body_salt_scrub |
| q05 | exact_term | unchanged | 1 | lost_property, waiting_list |
| q06 | exact_term | unchanged | 1 | — |
| q07 | exact_term | unchanged | 1 | spa_day_sunday, spa_day_half_morning, spa_day_duo |
| q08 | exact_term | unchanged | 1 | cancellation_group_bookings, cancellation_private_hire, cancellation_workshops |
| q09 | exact_term | unchanged | 1 | cancellation_group_bookings, spa_day_duo |
| q10 | exact_term | unchanged | 1 | facial_mens_essential, facial_collagen_firm |
| q11 | semantic | unchanged | 1 | massage_foot_reflex |
| q12 | semantic | unchanged | 1 | pets_policy, accessibility |
| q13 | semantic | unchanged | 1 | cancellation_courses, cancellation_workshops |
| q14 | semantic | unchanged | 5 | — |
| q15 | semantic | unchanged | 1 | spa_day_essential, cancellation_spa_days, spa_day_half_morning |
| q16 | semantic | unchanged | 1 | accessibility, pets_policy |
| q17 | semantic | unchanged | 1 | facial_age_focus, facial_purify_balance, facial_collagen_firm |
| q18 | semantic | unchanged | 1 | massage_warm_bamboo, massage_aroma_candle, facial_collagen_firm |
| q19 | multi_fact | unchanged | 2 | massage_aroma_candle |
| q20 | multi_fact | unchanged | 1 | accessibility |
| q21 | multi_fact | unchanged | 1 | cancellation_courses, cancellation_group_bookings, cancellation_workshops |
| q22 | multi_fact | unchanged | 1 | massage_scalp_and_neck, spa_day_duo |
| q23 | multi_fact | unchanged | 1 | spa_day_duo |
| q24 | multi_fact | unchanged | 2 | spa_day_sunday, facial_express_refresh, massage_thai_oil |
| q25 | out_of_scope | unchanged | n/a | see §3 |
| q26 | out_of_scope | unchanged | n/a | see §3 |
| q27 | out_of_scope | unchanged | n/a | see §3 |
| q28 | out_of_scope | unchanged | n/a | see §3 |
| q29 | out_of_scope | unchanged | n/a | see §3 |
| q30 | out_of_scope | unchanged | n/a | see §3 |

### Notes on individual rows

- **q01 (rank 4).** `massage_himalayan_salt_stone` (75 min, €102) and
  `massage_herbal_poultice` (80 min, €118) now outrank the document
  holding the Hot Stone price (75 min, €95). Neither answers the
  question. This is the intended failure mode: same cluster, wrong
  member, confidently wrong number.
- **q04.** `body_algae_detox_wrap` (€88) was written deliberately as a
  near-name collision with the Seaweed Wrap (€80) that q04 asks about.
  The annotated document still ranks 1.
- **q14 (rank 5).** The four documents above it are all **original**;
  no new document is involved. q14 was already marginal before the
  expansion — it was the one retrieval miss in the pre-expansion
  `hybrid` run. The expansion did not cause this and did not worsen it.
- **q24 (rank 2).** `spa_day_sunday` outranks the annotation on the word
  "Sunday". It is a package, not private hire, so it does not answer the
  question.

---

## 5. Validator

`python src/validate_testset.py` passes:

```
OK  62 documents, 65 questions, every expected_doc_id resolves.
```

Two warnings, both benign:

1. **20 documents that no question points at.** Deliberate. A confusable
   cluster needs members that exist only to be wrong answers — a
   distractor nobody asks about is doing its job.
2. **`spa_day_sunday.md` contains "our other"** — the crude grep for a
   second location firing on "served later than on our other packages".
   A false positive. The phrase refers to other packages, not other
   premises.

The validator's expected counts were updated: 18 → 62 documents,
10/8/6/6 → 29/15/12/9 questions. Three new forbidden subjects were added
to it for q61–q63: nail treatments, accommodation, and treatments at the
customer's home.

---

## 6. Lexical overlap — measured separately

The added questions were written while reading their source documents,
which imports that vocabulary and structurally favours sparse retrieval
— a confound pointing in the same direction as this benchmark's expected
conclusion.

It was measured, found real, and partly corrected: a genuine **+24 point
confound in `multi_fact`**, removed by rewriting six questions in
customer voice, leaving **+1.7 points** once standardised for category
mix. `exact_term` showed no bias at all (88% against 88%) and was
deliberately left alone.

**Full hypothesis, method, figures and conclusion:
[`testset-bias-check.md`](testset-bias-check.md).** Not repeated here —
two copies of a measurement diverge, and the stale one is always the one
being read.

---

## 7. What is not covered by this review

- The **36 new questions** are not annotation-reviewed here the way the
  original thirty are. Their expected answers were taken verbatim from
  the source document at the time of writing.
- **No run has been made against the expanded corpus.** Every number in
  this document is a retrieval rank, not a benchmark result.
- The **judge** was measured at 98.9% self-agreement (89/90 verdicts
  reproduced on replay) before the expansion. That figure is from the
  saturated corpus and does not necessarily carry over; it is re-measured
  against the expanded corpus by `src/judge_stability.py`. Full analysis,
  including the one flip and what it exposes about the judge's design:
  [`judge-reliability.md`](judge-reliability.md).

## 8. q03 — decided

Left exactly as annotated, unchanged and un-dropped: a retrieval miss
across all three configurations is an honest result and belongs in the
README as a failure mode retrieval cannot fix.

**q66** was added beside it — "How many hours ahead do I need to cancel
a single treatment?", annotated to `cancellation_policy` with the same
expected answer. Naming the booking type gives the measurable version of
the question next to the realistic one, so the pair separates "the
retriever cannot find the default" from "the customer did not say which
booking they meant".
