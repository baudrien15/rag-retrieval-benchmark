# The escalation detector

The workflow has to decide, per answer, whether to serve it or hand the
conversation to a human. The benchmark's `escalated` flag cannot make
that decision: it is produced by the judge, from the reference answer,
after the run. At serving time there is no reference answer.

This is the substitute, and the point of this document is that it was
**measured rather than asserted** — the same standard the rest of the
repository holds itself to.

## What it is not

**It does not touch generation.** `GENERATION_SYSTEM` and
`GENERATION_PARAMS` are the constants held byte-identical across the
three benchmark runs. Asking the generator to emit a structured
`{"answered": false}` field would have changed them, and every published
number would have stopped being reproducible against the code that
produced it.

**It is not a second model call.** A classifier LLM reading the answer
would add latency, cost and a model dependency to the demo, for a
component nothing has measured.

**It is not a confidence threshold.** That was tested in phase 4 and
rejected — see [`threshold-analysis.md`](threshold-analysis.md) and
decision 6 in [`../DECISIONS.md`](../DECISIONS.md).

## The rule

A pure function, [`src/escalation.py`](../src/escalation.py), returning
`True` when the answer states that **the knowledge source does not hold
the answer**. Four patterns, one idea:

| # | Shape | Example matched |
|---|---|---|
| 1 | documents + negation + knowledge verb | "The documents don't cover laser hair removal." |
| 2 | negation + past participle + documents | "…which aren't covered in these documents." |
| 3 | pronoun subject in a later sentence | "The documents only cover Nantes. They don't mention any other locations." |
| 4 | first-person lack of knowledge or standing | "I don't have information about…", "I can't answer that", "I'm not qualified to…" |

**What is deliberately not matched** is the reason a substring search for
"reception" or "sorry" fails. All of the following appear in `dense`
answers the judge scored as *answered*:

- "Contact reception to book" — a next step, not a refusal
- "We cannot extend a card once it has expired" — a negative fact
- "we do not admit anyone under 16" — a negative fact
- "we cannot promise it" — hedging a positive answer

The subject of the negation is what separates them: the documents or the
assistant's own knowledge, never the spa's policy.

**Ambiguity resolves to escalation.** An empty answer, a whitespace-only
answer, or the API-refusal marker all return `True`. The failure that
matters is serving a fabricated answer to a customer; putting one
answerable question in front of an agent costs an agent a minute.

## The split

| Set | Artefacts | Used for |
|---|---|---|
| Development | `2026-08-18T093939Z-dense.json`, `2026-08-18T083135Z-dense.json` | writing the rule |
| Evaluation | `2026-08-18T093939Z-hybrid.json`, `2026-08-18T093939Z-hybrid_rerank.json`, `2026-08-18T083135Z-hybrid.json`, `2026-08-18T084052Z-hybrid_rerank.json` | measuring it |

The `hybrid` and `hybrid_rerank` artefacts were not opened until the rule
was frozen. Reproduce with `python src/escalation_eval.py`.

### Where the row counts come from

Each artefact holds **exactly one row per question** — checked, no
duplicated judge passes, no repeated ids. The counts are two benchmark
runs on two corpora:

| | Questions | × configurations | Rows |
|---|---|---|---|
| Run 1, pre-expansion (18 documents) | 30 | 3 | 90 |
| Run 2, expanded (62 documents) | 66 | 3 | 198 |
| | | | **288** |

Development takes the two `dense` columns (66 + 30 = **96 answers**),
evaluation the four `hybrid` and `hybrid_rerank` columns (**192
answers**). The 198 figure quoted for judge agreement elsewhere in this
repository is run 2 alone; it is not the same denominator.

### The split is by configuration, not by question

**All 66 questions appear in both sets.** Only the answers differ: the
rule was written on `dense`'s answer to q25 and evaluated on `hybrid`'s
answer to the same q25. Retrieval changes which documents the generator
sees, so the texts genuinely differ — but the phrasing of a declination
is driven mostly by the question and the prompt, and those are identical.

**A row count therefore overstates the evidence twice over**: once
because the same question recurs across configurations, and again
because q01–q30 recur across the two runs.

## The measurement

Two rates, reported separately, with three denominators rather than one.

### Development set — the rule was written on these

| | Answers | Distinct questions |
|---|---|---|
| Total | 96 | 66 |
| Judged escalations | 21 | 14 |
| Judged answers | 75 | 55 |
| **Missed escalations** (detector `False`, judge `True`) | **0 / 21** | |
| **Wrong escalations** (detector `True`, judge `False`) | **0 / 75** | |

### Evaluation set — a different configuration, the same questions

| | Answers | Distinct questions |
|---|---|---|
| Total | 192 | 66 |
| Judged escalations | 37 | 14 |
| Judged answers | 155 | 57 |
| **Missed escalations** (detector `False`, judge `True`) | **1 / 37** | |
| **Wrong escalations** (detector `True`, judge `False`) | **0 / 155** | |

### The number that actually carries weight

Of the 14 questions that escalate in the evaluation set, **11 already
escalated in the development set** — their declination phrasing was
visible while the patterns were being written. Three did not: q01, q24,
q66.

| | Count |
|---|---|
| Answers to questions that never escalated in development | **4**, over **3 distinct questions** |
| Caught | **3 / 4** (q01 `hybrid`, q24 `hybrid_rerank` ×2) |
| Missed | **1 / 4** (q66 `hybrid`) |

**This is the only part of the evaluation the rule cannot have been
fitted to, and it is four answers.** It supports "the rule generalises a
little" and nothing stronger. The 1/37 above is the honest count of
artefact rows; it is not 37 independent tests.

**No aggregate agreement rate is given, and that is deliberate.** Judged
escalations are 37 of 192 answers. A detector that returned `False`
unconditionally would score 81% agreement while missing every escalation
there is. The two rates measure different failures against different
denominators and cannot be averaged into anything meaningful.

## The one disagreement

**q66, `hybrid`, `exact_term`** — judge `True`, detector `False`:

> "The documents provided cover cancellation terms for treatment
> courses, group bookings, and spa day packages, **but not for single
> individual treatments**. Please contact reception for the cancellation
> terms that apply to your booking."

The declination is real but inverted in form: the sentence states what
the documents *do* cover and appends the exclusion. None of the four
patterns reach an affirmative clause carrying a trailing "but not for".

**The rule was not amended to catch it.** Fixing a case found in the
evaluation set would fold that set into the development set, and the
1/37 above would stop being an out-of-sample number. It is recorded as
the known failure mode instead.

That case is q66, the sister question of q03 — the pair is reported
together in [`../RESULTS.md`](../RESULTS.md) under decision 2 of
[`../DECISIONS.md`](../DECISIONS.md). Detector against judge across the
pair, expanded run:

| Config | q03 judge / detector | q66 judge / detector |
|---|---|---|
| `dense` | True / **True** | False / **False** |
| `hybrid` | False / **False** | True / **False** ← the miss |
| `hybrid_rerank` | False / **False** | False / **False** |

## Limits

- **The genuinely held-out evidence is four answers.** Everything else
  in the evaluation set is a question whose declination the rule had
  already seen in another configuration. Three of four caught bounds
  nothing.
- **37 judged escalations is a small denominator, and they are not
  independent.** One miss is 2.7% of rows; the next miss would double
  it.
- **A question-level split was not available.** It would have meant
  writing the rule on part of the test set and evaluating on the rest,
  which is the better design and is what a rerun should do. The split
  used here was chosen before this was noticed, and the numbers are
  reported at the strength that split supports rather than restated at
  the strength the row counts suggest.
- **The judge is the reference, and the judge is not ground truth.** Its
  own `escalated` field reproduced at 100% across two passes (198/198,
  see [`judge-reliability.md`](judge-reliability.md)), which is the best
  available reference here but still not a human panel.
- **The rule is English-only and prompt-specific.** It matches the way
  this generation prompt is instructed to decline. A different prompt
  needs the measurement rerun, not the rule reused.

Artefact: `../reports/runs/2026-08-18T155129Z-escalation-detector.json`.
