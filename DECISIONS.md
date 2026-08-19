# DECISIONS.md — Closed decisions and reading reserves

This file records decisions taken **outside the repository**. They cannot
be derived from the code, the documents or the git history, and they are
not open for re-litigation.

Two kinds of entry live here:

- **Closed decisions** — settled. Do not reopen them, do not propose an
  alternative, do not "improve" them in passing.
- **Reading reserves** — constraints on how the measured results may be
  described. They bind **every text produced in this repository**,
  including the README, commit messages and any generated report.

---

## Closed decisions

1. **The judge stays unchanged.** It is *not* given the retrieved
   documents. Handing the judge the same context the generator saw would
   make the evaluation circular — it would grade the answer against the
   retrieval that produced it, rather than against the reference.

2. **q03 is left ambiguous**, annotated according to reading 1. **q66 is
   its sister question** and must be reported together with it. Neither
   is silently resolved.

3. **`exact_term` was not rewritten** during the lexical bias check. The
   category is reported as it was written.

4. **Pre-registration is abandoned.** Do not reintroduce it.

5. **Qdrant runs locally**, not on the VPS.

6. **No confidence threshold is adopted in production.** The gate on the
   reranker score catches 100% of out-of-scope questions but costs 12% of
   valid answers. That cost is judged too high. The result is kept as a
   **measurement, not as a component** — see
   [`docs/threshold-analysis.md`](docs/threshold-analysis.md).

---

## Reading reserves

**`hybrid_rerank` ahead of `dense` — conclusive.** 89% `answer_correct`
in both judge passes, no flip between them, six points of margin.

**`dense` versus `hybrid` — NOT conclusive.** The ranking inverts between
the two judge passes. **Writing that `hybrid` improves retrieval — or any
equivalent phrasing — is forbidden anywhere in this repository.**

**`hit@1` (91%) and the `hybrid` drop on `multi_fact` (67% against 92%)
are exact, with no reserve.** These metrics do not pass through the
judge and carry none of its uncertainty.

**Judge agreement: 98.5% (195/198)**, with the variance concentrated on a
single mechanism.

**The fabrication rate is never written as "0%".** The mandatory
phrasing, everywhere including the README, is a count with its
denominator:

> no fabrication observed on N out-of-scope questions

followed by the bound. A bare "0%" states a precision the sample size
does not support.

Two denominators are now in play, and each belongs to its own
measurement:

| Denominator | Where it applies | 95% bound (rule of three) |
|---|---|---|
| **9** | the `out_of_scope` category of run 2026-08-18-2, in `RESULTS.md` | ~33% |
| **20** | the out-of-scope probe of 2026-08-19, `data/oos_probe.json` | ~15% |

The probe was added on 2026-08-19 because the denominator, not the
observation, was the weak part. It leaves `data/testset.json` frozen and
moves no other metric. **The principle is unchanged** — count,
denominator, bound — only the best available denominator improved. Quote
the 20 where the claim is about fabrication generally; quote the 9 where
the claim is about the benchmark run's `out_of_scope` category.
