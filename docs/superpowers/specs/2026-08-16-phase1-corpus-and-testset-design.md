# Phase 1 design — corpus and test set

Date: 2026-08-16
Status: approved, implemented

## Purpose

Phase 1 produces the two artefacts every later number depends on: a
corpus of 18 documents and 30 annotated questions. A mis-annotated
`expected_doc_ids` does not fail loudly — it silently makes the report
lie. This document records the decisions so they can be audited later.

## Corpus

18 documents, one document per chunk, each short enough for that to be
reasonable (roughly 120–220 words).

| Group | Documents |
|-------|-----------|
| Pricing | `pricing_massage`, `pricing_facials`, `pricing_body_rituals` |
| Treatments | `treatments_massage`, `treatments_facials`, `treatments_body`, `treatments_signature` |
| Policies | `cancellation_policy`, `booking_and_payment`, `gift_cards`, `memberships`, `contraindications` |
| Practical | `opening_hours`, `location_and_access`, `facilities`, `first_visit`, `house_rules`, `groups_and_events` |

### Overlap is deliberate, planted traps are not

The corpus contains documents that compete with each other, because a
real spa's content does:

- **Three price lists** rather than one, split by treatment family. So
  "how much is X" requires picking the right list among three that are
  lexically very similar.
- **"Deep Tissue Massage" and "Deep Relax Aromatherapy Massage"** are
  two genuinely different treatments with adjacent names.
- **Prenatal massage** appears in `treatments_massage` and in
  `contraindications`, from two different angles.

Rejected alternative: planting near-identical names and numbers
specifically to break dense retrieval. It would produce a wider gap and
a worthless benchmark — the first serious reader would say the corpus
was built to yield the advertised result.

Also rejected: one topic per document with no overlap. Clean to
annotate, but dense retrieval would do well and the experiment would
show nothing.

### Writing rule: each fact is stated once

A number appears in exactly one document. `booking_and_payment` refers
to the cancellation terms without restating "24 hours";
`pricing_body_rituals` gives the Signature Journey price without its
duration.

Without this rule two documents answer a question equally well,
`expected_doc_ids` becomes a coin flip, and `hit@3` measures the
annotation rather than the retrieval.

Prices live in `pricing_*`, durations live in `treatments_*`. Two
exceptions, both deliberate and neither covered by a question:
membership fees live in `memberships` (they are not treatment prices),
and the facilities day pass lives in `facilities`.

## Test set

30 questions, fixed order `q01`–`q30`.

### `exact_term` — 10

All three price lists are probed. That is the point of the category: if
only one list were tested, a single lucky retrieval would carry the
whole category.

| id | Question | `expected_doc_ids` |
|----|----------|--------------------|
| q01 | How much is the hot stone massage? | `pricing_massage` |
| q02 | How long does the Lumen Signature Journey take? | `treatments_signature` |
| q03 | How many hours ahead do I need to cancel? | `cancellation_policy` |
| q04 | What does the seaweed wrap cost? | `pricing_body_rituals` |
| q05 | How long is a gift card valid? | `gift_cards` |
| q06 | How much is the monthly Serenity membership? | `memberships` |
| q07 | What time do you open on Sunday? | `opening_hours` |
| q08 | Minimum group size for a private booking? | `groups_and_events` |
| q09 | How much deposit is taken at booking? | `booking_and_payment` |
| q10 | What does the Hydraglow facial cost? | `pricing_facials` |

### `semantic` — 8

No corpus term appears in the question wording.

| id | Question | `expected_doc_ids` |
|----|----------|--------------------|
| q11 | Training hard, legs are wrecked — suggestion? | `treatments_massage` |
| q12 | Can I bring my children? | `house_rules` |
| q13 | What happens if I turn up late? | `cancellation_policy` |
| q14 | Anywhere to unwind before my treatment? | `facilities` |
| q15 | Never been to a spa — what should I know? | `first_visit` |
| q16 | How do I get to you without a car? | `location_and_access` |
| q17 | My skin looks dull, anything that would help? | `treatments_facials` |
| q18 | I'd like to give this as a present. | `gift_cards` |

q03 and q13 both target `cancellation_policy` from different angles.
Deliberate: it gives a direct `exact_term` vs `semantic` comparison on
an identical document.

### `multi_fact` — 6

Exactly two documents each, never three — with three, `hit@3` is
satisfied trivially.

| id | Question | `expected_doc_ids` |
|----|----------|--------------------|
| q19 | I'm pregnant — which massage can I book? | `contraindications`, `treatments_massage` |
| q20 | Signature Journey price and time to allow? | `pricing_body_rituals`, `treatments_signature` |
| q21 | On Serenity — charged if I cancel late? | `memberships`, `cancellation_policy` |
| q22 | Deposit amount, and can a gift card cover it? | `gift_cards`, `booking_and_payment` |
| q23 | Surgery six weeks ago — can I use the sauna? | `contraindications`, `facilities` |
| q24 | Eight of us, place to ourselves — a Sunday? | `groups_and_events`, `opening_hours` |

Two of these needed correcting after the first draft, because one
document answered them on its own:

- q19 originally worked from `contraindications` alone, which named the
  prenatal treatment outright. That document now says only that one
  massage on the list is written for pregnancy, and points at the
  treatment descriptions for which.
- q22 was "can I pay the deposit with a gift card?", answerable "no"
  from `gift_cards` alone. Asking the amount as well forces
  `booking_and_payment` into the answer.

The general trap: a `multi_fact` question whose *binary* answer sits in
one document is not multi-fact, whatever its `expected_doc_ids` says.

A second review pass, reading each `expected_answer` back against the
documents it cites, caught two more. Both passed every automated check —
the strings were all present — and both were wrong in their reasoning:

- **q21** asserted that a late-cancelled membership session "does not
  carry over". `memberships` says an *unused* session does not carry
  over, and separately that a *late-cancelled* one counts as used. A
  session that counts as used is not an unused one, so the carry-over
  rule does not reach it. The reference answer now claims only what the
  two documents jointly support.
- **q24** was "there are eight of us, can you take us on a Sunday?".
  `groups_and_events` describes two regimes — group bookings from four
  people with two weeks' notice, and private hire from eight with three
  weeks'. The question did not say which, and the reference answer
  assumed private hire. A model answering about group bookings would
  have been judged wrong while being right. The question now says the
  party wants the place to itself.

This is the failure mode worth naming: a reference answer can be built
entirely from strings that appear in the corpus and still be false,
because it joins two facts that do not join. Automated checking cannot
see it. The check is to read each answer against its documents and ask
what else a reasonable customer could have meant.

### `out_of_scope` — 6

All near-domain: plausible customer questions the corpus genuinely does
not cover. Obviously unrelated questions (weather, car repair) were
rejected — every configuration would escalate correctly and
`fabrication_rate` would separate nothing.

| id | Question | Document that will still rank high |
|----|----------|------------------------------------|
| q25 | Do you offer laser hair removal? | `treatments_body` |
| q26 | Will my health insurance reimburse the massage? | `booking_and_payment` |
| q27 | Do you have a branch in Bordeaux? | `location_and_access` |
| q28 | Can you invoice my employer directly? | `booking_and_payment` |
| q29 | Lower back hurting three weeks — what's causing it? | `contraindications` |
| q30 | Do you sell the oils you use? | `treatments_body` |

### Forbidden topics

These six subjects must never be covered by any corpus document. If one
is added later, the corresponding question stops being out of scope and
the annotation becomes false.

1. Laser hair removal, or any treatment not on the price lists
2. Health insurance, reimbursement, mutuelle
3. Any second location, branch, or franchise — in particular
   `location_and_access` must not say "our only location", since that
   sentence alone would answer q27
4. Corporate invoicing, purchase orders, B2B billing
5. Medical diagnosis of a symptom. `contraindications` states who
   should avoid what; it never explains what a symptom means
6. Retail sale of oils or products — `treatments_body` and `facilities`
   must not mention a shop

Re-read this list against the corpus whenever a document is edited.

## `treatments_body` points nowhere on purpose

No question lists `treatments_body` in its `expected_doc_ids`, and the
checker reports this. It is intended.

The document describes the Seaweed Wrap at length without giving its
price. q04 asks what the seaweed wrap costs, and the answer is in
`pricing_body_rituals`. A dense retriever comparing the question against
the two documents has every reason to prefer the one that talks about
seaweed wraps in detail — which is the exact-term failure mode the whole
benchmark exists to measure.

Removing the document to make the checker quiet would remove the trap.

## Verification

`python src/validate_testset.py` — standard library only, no new
dependency. It checks that every `expected_doc_id` resolves to a file,
that the category split is 10/8/6/6, that ids run `q01`–`q30` in order,
that `out_of_scope` questions carry no documents and no expected answer,
that `multi_fact` questions carry exactly two documents and the other
answerable categories exactly one, and it greps the corpus for the six
forbidden subjects.

Run it after any edit to a corpus filename or to the test set.

## Out of scope for phase 1

No ingestion, no retrieval, no generation. Phase 1 ends with 18 markdown
files, a populated `data/testset.json`, and a consistency check between
them.
