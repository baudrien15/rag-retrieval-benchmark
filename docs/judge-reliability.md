# How reliable is the judge?

**Date:** 2026-08-18
**Script:** `python src/judge_stability.py reports/runs/*.json`
**Artefacts:** `reports/runs/2026-08-18-judge-stability-pre-expansion.json`,
`reports/runs/2026-08-18-judge-stability-expanded.json`

`answer_correct` and `fabrication_rate` — two of the four metrics — are
produced by an LLM judge. Every number published through them is only as
trustworthy as that judge is repeatable. This document measures it
rather than assuming it.

The headline is not the agreement rate. It is **where the disagreement
lives**: every single flip across two corpora comes from one nameable
mechanism, and that mechanism also produces errors the agreement rate
cannot see.

---

## Why it needs measuring at all

CLAUDE.md specifies the judge at **temperature 0**. That is not
achievable: **Claude Opus 5 removed the `temperature` parameter** and
returns a 400 on any value.

The nearest available substitute is used instead — thinking disabled,
`effort: "low"`, and a schema-constrained verdict, which together remove
the largest sources of run-to-run variation. But "nearest available
substitute" is not "deterministic", and the difference is an empirical
question.

The generator, Claude Haiku 4.5, does still accept `temperature` and
runs at 0 as specified. Only the judge is affected.

---

## Method

A **pure replay**. The run artefacts persist every generated answer, so
each stored answer is sent to the judge a second time with exactly the
same inputs it saw the first time — no question regenerated, no
retrieval repeated, the same prompt and the same reference answer.
Anything that differs between the two verdicts is the judge alone.

Both boolean fields are reported separately, since `correct` drives
`answer_correct` and `escalated` drives `fabrication_rate`.

---

## Results — both corpora

| | Pre-expansion | Expanded |
|---|---|---|
| Corpus / test set | 18 docs, 30 questions | 62 docs, 66 questions |
| Judgements replayed | 90 | 198 |
| `correct` agreement | **98.9%** (89/90) | **98.5%** (195/198) |
| `escalated` agreement | **100%** (90/90) | **100%** (198/198) |
| Verdict flips | 1 | 3 |

Reliability held up as the questions got harder — 98.9% against 98.5% is
the same figure within its own noise. **`escalated` has not disagreed
once in 288 judgements.**

### What that permits, and what it forbids

Roughly **one flip per 66 judgements**, i.e. about one question per
configuration per run. Applied to the expanded run:

| Comparison | Gap | Verdict |
|---|---|---|
| `hybrid_rerank` 89% vs `dense` 83% | 6 pts ≈ 4 questions | **Above noise. A result.** |
| `hybrid` 85% vs `dense` 83% | 2 pts ≈ 1.3 questions | **At the noise floor. Not a result.** |

The second is confirmed directly rather than by argument. Recomputing
`answer_correct` from the second pass's verdicts:

| Config | pass 1 | pass 2 | delta |
|---|---|---|---|
| `dense` | 83% | 82% | −1.5 pt |
| `hybrid` | 85% | **88%** | +3.0 pt |
| `hybrid_rerank` | **89%** | **89%** | 0.0 pt |

The `dense`/`hybrid` ranking **inverts** between two runs of the same
judge on identical inputs. `hybrid_rerank`'s lead does not move at all.

Flips ran 1 `True→False` and 2 `False→True`, so no configuration is
systematically favoured. This is noise, not bias.

**`hit@1` and `hit@3` do not pass through the judge and carry none of
this uncertainty.**

---

## The finding: variance has exactly one source

All three flips on the expanded corpus are the same mistake. In each,
the judge marked an answer wrong for supplying figures it called
unverified — and **in each case the figures are in the corpus.**

### q55 — `dense`, semantic — `True → False`

> "The assistant added unverified specifics (30 minutes, €40, shower,
> sauna/hammam inclusion) not supported by the reference, risking
> fabricated figures."

`body_mineral_soak` states 30 minutes at €40, a shower in the same room,
and the facilities inclusion. All four correct.

### q10 — `hybrid`, exact_term — `False → True`

> "The price and duration match, but the assistant fabricated
> unsupported details about facility access and a six-session course
> price and expiry."

`pricing_facials` states that a course of six is "charged at five times
the single-treatment price" (€90 × 5 = €450), that it "must be used
within twelve months", and that prices include the facilities. All three
correct.

### q24 — `hybrid`, multi_fact — `False → True`

> "The assistant added unverified specifics (€1,200 for three hours,
> therapist per two guests, 50% deposit) not supported by the reference,
> constituting fabrication despite the correct core facts."

`groups_and_events` states private hire "starts at €1,200 for a
three-hour slot", "a therapist for every two guests", and "a 50% payment
at the time of booking". All three correct.

**Nine details across three cases. All nine are in the corpus. The
assistant was right every time.**

### The mechanism

`JUDGE_SYSTEM` tells the judge that "extra correct detail is fine".
**The judge cannot comply with that instruction.** It is shown only the
question, the reference answer, and the assistant's answer — never the
corpus. It cannot distinguish correct extra detail from invented extra
detail, so it guesses, and the guess is where every unit of variance
lives.

The judge is stable everywhere except at the one point where the prompt
asks it to do something it lacks the information to do.

---

## The same mechanism also produces stable errors

The agreement rate cannot see this, and it is the more serious half.

**q03, `hybrid_rerank`.** Retrieval worked perfectly — `cancellation_policy`
came back at rank 1. The assistant answered:

> It depends on what you've booked:
> - Individual treatment: 24 hours
> - Spa day package: 72 hours
> - Treatment course: 48 hours

That is a **better answer than the reference**, which gives only the
24-hour figure. All three periods are correct: `cancellation_policy`,
`cancellation_spa_days` and `cancellation_courses` respectively. The
judge said:

> "The assistant invented tiered notice periods (72/48 hours) not in the
> reference and omitted the 50% late-cancellation charge."

Marked wrong. **Both passes agreed**, so it never appears as a flip and
contributes nothing to the 1.5% disagreement rate — it is a silent,
reproducible error in exactly the same mechanism.

The implication: **98.5% agreement is an upper bound on reliability, not
an estimate of accuracy.** A judge that is consistently wrong scores
100% here. This case was found by reading the stated reasons, which is
why `src/judge_stability.py` records both passes' reasoning in its
artefact rather than only the booleans.

---

## Why the judge is not being fixed

The obvious repair is to show the judge the retrieved documents. **It
would be worse than the disease.**

A configuration that retrieves badly would have its answers validated
against the poor documents it retrieved. An answer grounded in the wrong
document would be graded as correct because it faithfully reflects what
was fetched — which makes fabrication *invisible* precisely where the
benchmark exists to count it. The check becomes circular.

**Corpus-wide access** would be the correct fix: the judge sees all 62
documents and can verify any figure against any of them, with no
coupling to what was retrieved. It is not being made, for two reasons.
It changes what `answer_correct` measures mid-project, and it does not
change any conclusion currently drawn — the one comparison that clears
the noise floor (`hybrid_rerank` over `dense`) is stable under both
judging passes.

Recorded as a known limitation, deliberately left in place.

---

## What is still unmeasured

- **Two passes measure repeatability, not accuracy.** See the q03 case
  above: a reproducible error scores as perfect agreement.
- The replay uses the **same prompt** both times. Sensitivity to prompt
  rewording is a separate and probably larger source of variation,
  entirely unmeasured here.
- Both figures come from **two passes**, not many. A third pass would
  tighten the interval; the direction of the conclusion would not
  change, since the decisive comparison survived a full ranking
  inversion in the comparison next to it.
