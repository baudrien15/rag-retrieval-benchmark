# RAG Retrieval Benchmark

Measuring how much retrieval strategy — not prompting — drives answer
quality and hallucination rate in a support chatbot.

> Status: phases 1-4 complete. Every number below comes from a committed
> run artefact in [`reports/runs/`](reports/runs/), and every table row
> in [`RESULTS.md`](RESULTS.md) cites the file it came from.

## Why

"The chatbot gives inaccurate answers" is usually diagnosed as a prompt
problem and fixed by prompt tuning. In my experience it is more often a
retrieval problem: dense-only vector search misses exact terms — prices,
product names, reference numbers — and the model then answers from
whatever it was given.

This repository tests that claim on a controlled corpus instead of
asserting it.

## Method

A synthetic corpus for a fictional wellness centre (a domain dense in
exact terms) — **62 documents built around deliberate confusable
clusters**: twelve massages described in near-interchangeable prose with
twelve different prices, several treatment tiers, cancellation windows
that differ by booking type. That structure is the experiment. A corpus
of clearly distinct documents cannot distinguish retrieval methods,
because dense similarity is sufficient when every question maps to a
semantically unique document — see
[`docs/saturation-and-expansion.md`](docs/saturation-and-expansion.md).

66 questions annotated with the documents that should answer them, split
into four categories: exact-term lookup, semantic paraphrase,
multi-document, and out-of-scope.

Three configurations are compared:

| ID | Retrieval |
|----|-----------|
| `dense` | Dense vector search only |
| `hybrid` | Dense + sparse, fused with RRF |
| `hybrid_rerank` | Dense + sparse + reranking |

Four metrics: **`hit@1`** and `hit@3` for retrieval, judged answer
correctness, and fabrication rate on out-of-scope questions. All
reported per category, never only in aggregate.

**`hit@1` is the headline retrieval metric, and `hit@3` saturates at the
top of the table** — `hybrid_rerank` scores 100% hit@3, so that metric
can no longer separate the best configuration from a better one. hit@1
is also where the failure that matters shows up: retrieving the right
cluster but the wrong member yields a confidently wrong figure, and
hit@3 scores it as a hit.

### Controlling for the model

The generation model is **deliberately modest and held constant** across
all three runs. A stronger model compensates for poor retrieval by
inferring around gaps, which compresses the difference between
configurations and would make the comparison meaningless. The reported
delta therefore reflects retrieval quality, not model quality.

The judge is a different model from the generator, since models tend to
favour their own output. **Its repeatability is measured, not assumed**:
98.5% self-agreement over 198 replayed verdicts, with every observed
disagreement traced to one mechanism —
[`docs/judge-reliability.md`](docs/judge-reliability.md). That figure is
what decides which differences below are readable and which are noise.

## Results

62 documents, 66 questions, three configurations. Full tables, per
category, with every row citing its run artefact: [`RESULTS.md`](RESULTS.md).

| Config | hit@1 | hit@3 | Answer correct | Fabrication (n=9) |
|--------|-------|-------|----------------|-------------------|
| `dense` | 88% | 95% | 83% | 0 / 9 |
| `hybrid` | 84% | 93% | 85% | 0 / 9 |
| **`hybrid_rerank`** | **91%** | **100%** | **89%** | 0 / 9 |

Fabrication is reported as a count, not a rate: **no fabrication was
observed on 9 out-of-scope questions** per configuration in this run. At
that sample size the true rate is bounded at roughly **33% at worst**
(rule of three, 95% confidence interval), so a bare "0%" would state a
precision the measurement does not have.

That denominator was the weakest number here, so it was **measured
again on a bigger one**: a separate 20-question out-of-scope probe, same
models and parameters, returned **no fabrication on 20 questions** per
configuration — 60 asked, none answered instead of escalated. The bound
tightens from 33% to roughly **15%**. The probe leaves `data/testset.json`
frozen and changes no other metric; see the probe section in
[`RESULTS.md`](RESULTS.md).

**Reranking is the only intervention that pays.** Its gain over `hybrid`
(93% → 100% hit@3) is the signature of a reranker working as intended:
it finds no new documents, it reorders the same candidates that RRF had
already fetched and mis-ranked.

**The prediction this project was built on is refuted.** Dense-only
retrieval was expected to underperform on exact-term questions. It does
not: `dense` and `hybrid` both score **90% hit@1** there. Adding sparse
retrieval bought nothing on exact terms, even against twelve
near-identical massage documents with twelve different prices. What
unlocks the category is reranking (97%), not lexical matching.

**Adding sparse retrieval can cost you.** `hybrid` is the *worst*
configuration for retrieval at 84% hit@1, and the damage is localised:
**67% against 92% on multi-document questions.** RRF promotes a
lexically similar sibling into rank 1 and displaces one of the two
documents the answer needs.

**Do not read the `dense` vs `hybrid` answer-correct gap.** 83% against
85% is about 1.3 questions against a ~1 question judge-noise floor, and
the ranking inverts under a second judging pass. `hybrid_rerank`'s lead
is stable under both.

> **The `answer correct` column understates every configuration.** The
> judge never sees the corpus, so it cannot tell correct extra detail
> from invented detail and penalises both. The direction of the bias is
> known, its size is not, and **no number has been adjusted to
> compensate**. See the section below.

### A failure retrieval cannot fix

Two questions asking the same thing — "How many hours ahead do I need to
cancel?" and the same question naming a single treatment. The corpus
holds six different cancellation windows by booking type.

All three configurations answer the unqualified question wrongly, and
`hybrid` fails to retrieve the right document even when the booking type
*is* named. But `hybrid_rerank` retrieved the correct document at rank 1
and was still scored wrong — its answer enumerated all three periods
correctly, which is better than the reference answer, and the judge
called the extra figures invented. For the best configuration on this
question, the bottleneck was not retrieval. It was scoring.

## An agreement rate measures reproducibility, not accuracy

The most useful thing this project produced is not a comparison between
retrieval methods. It is a demonstration of how a benchmark can report a
confident number that is wrong in a way none of its own checks can see.

The judge was measured at **98.5% self-agreement** - 195 of 198 verdicts
reproduced exactly on replay. That number says the judge is
*consistent*. It says nothing about whether it is *right*. **A judge
that is consistently wrong scores 100%.**

**The worked example, q03 under `hybrid_rerank`.** Everything upstream
worked: the correct document was retrieved at **rank 1**. Asked "how
many hours ahead do I need to cancel?", the assistant answered:

> It depends on what you've booked: individual treatment 24 hours, spa
> day package 72 hours, treatment course 48 hours.

All three periods are correct and all three are in the corpus. Since the
question names no booking type, this is **a better answer than the
reference**, which gives only the 24-hour figure. The judge scored it
wrong, for "inventing tiered notice periods not in the reference".

It did not invent them. It correctly retrieved and reported them.

**Both judging passes agreed on that verdict.** So it never surfaced as
a flip, contributed nothing to the 1.5% disagreement rate, and is
invisible to every reliability figure in this repository. The agreement
rate reports perfect consistency here, and it was consistently wrong.

**What it costs, stated plainly:** `answer_correct` understates every
configuration; we cannot say by how much without hand-grading all 198
answers; and nothing has been adjusted to compensate. A correction
estimated from four observed cases would be a worse number than an
honestly biased one, because it would look precise.

Full analysis, including why showing the judge the retrieved documents
would make this worse rather than better:
[`docs/judge-reliability.md`](docs/judge-reliability.md).

## How this repository checks itself

Six self-checks, each producing a committed artefact rather than a
claim. Five are scripts anyone can rerun; the other was done by hand
because no script can do it.

| Check | Question it answers | Result |
|---|---|---|
| [`src/validate_testset.py`](src/validate_testset.py) | Does every `expected_doc_id` still resolve? Do the category counts hold? | passes: 62 documents, 66 questions |
| [`src/judge_stability.py`](src/judge_stability.py) | Is the judge repeatable? | 98.5% on `correct`, 100% on `escalated` - [`docs/judge-reliability.md`](docs/judge-reliability.md) |
| [`src/lexical_overlap.py`](src/lexical_overlap.py) | Were the newer questions phrased in a way that favours sparse retrieval? | a real **+24 point** confound found in `multi_fact` and removed; **+1.7 points** residual - [`docs/testset-bias-check.md`](docs/testset-bias-check.md) |
| [`src/escalation_eval.py`](src/escalation_eval.py) | Does the serving-time escalation detector agree with the judge on configurations it was not written against? | 1 missed escalation of 37 rows, 0 wrong escalations of 155 - but the split is by configuration, not by question, so the genuinely unseen evidence is **3 of 4 answers** - [`docs/escalation-detector.md`](docs/escalation-detector.md) |
| [`src/oos_probe.py`](src/oos_probe.py) | Is "no fabrication" an artefact of asking only 9 out-of-scope questions? | no - **0 fabrications on 20 questions** per configuration, bound tightened from 33% to ~15% - probe section of [`RESULTS.md`](RESULTS.md) |
| annotation review, by hand | Did expanding the corpus silently break an existing annotation? | one `out_of_scope` question was **nearly inverted** and caught - [`docs/annotation-review-expansion.md`](docs/annotation-review-expansion.md) |

The detector's single failure is q66, the question already recorded as
ambiguous before the detector was written.

The annotation review is the one worth dwelling on. Expanding the corpus from 18 to
62 documents introduced a sentence saying that a treatment's massage
candle is not taken home. That answers "do you sell the oils you use?",
an out-of-scope question whose correct behaviour is to escalate. An
assistant retrieving it would have been **right, and scored as a
fabrication**. No automated check could have caught it: a document that
answers an out-of-scope question contains no forbidden term. It was
found by reading 44 new documents against 30 existing questions.

## Confidence threshold

**There was nothing to threshold.** **No fabrication was observed on 9
out-of-scope questions** in any of the three configurations - 27
out-of-scope questions asked in total, not one answered instead of
escalated. At that sample size the true rate is bounded at roughly **33%
at worst** (rule of three, 95% confidence interval); the later
20-question probe brings that to roughly **15%**. At this scale and on
this corpus,
fabrication is not the dominant failure mode. Retrieving the wrong
member of a confusable cluster is, and a confidence threshold does not
help with that, because those answers come back with *high* scores.

The distributions were plotted anyway, because the transferable question
is whether a threshold would be workable on a corpus where fabrication
*is* a problem:

| Config | Best cutoff catches | at a cost of |
|---|---|---|
| `dense` | 78% of out-of-scope | 7% of answerable |
| `hybrid` | **44%** of out-of-scope | 12% of answerable |
| `hybrid_rerank` | **100%** of out-of-scope | 12% of answerable |

**A cross-encoder score is a usable confidence signal; an RRF score is
not.** The reranker separates the two populations by a wide margin
(+0.84 against -5.98 on average). The RRF score cannot, and the reason
is structural: it is a *rank fusion artefact, not a similarity*, so a
document ranking first in both branches scores at the maximum whether or
not it is relevant. A system that fuses with RRF and then thresholds on
the fused score is thresholding on noise.

Detail, plot and caveats:
[`docs/threshold-analysis.md`](docs/threshold-analysis.md).

## Running it

```bash
cp .env.example .env      # add your ANTHROPIC_API_KEY
docker compose up -d      # starts Qdrant locally on :6333
pip install -r requirements.txt

python src/ingest.py             # rebuild the collection from data/corpus/
python src/validate_testset.py   # corpus <-> testset consistency
python src/harness.py            # all three configs, writes reports/runs/
```

Reproducing the self-checks:

```bash
python src/lexical_overlap.py                      # test set bias
python src/judge_stability.py reports/runs/*.json  # judge repeatability
python src/score_distribution.py                   # threshold separation
```

## Limitations

Stated plainly, because a benchmark that hides its limits is not worth
much:

- Synthetic corpus. Real support corpora are messier, longer, and
  contradict themselves.
- 66 questions is enough to see a direction, not enough for tight
  confidence intervals. The out-of-scope category in the benchmark run
  is 9 questions, bounding the fabrication rate at roughly **33% at
  worst** (rule of three, 95% confidence interval). The separate
  20-question probe tightens that to roughly **15%** - better, and still
  not a rate that can be called zero.
- **`answer_correct` is biased downwards, in a known direction and an
  unknown quantity** - see the judge section above. `hit@1` and `hit@3`
  do not pass through the judge and carry none of that uncertainty.
- Chunking is fixed at one document per chunk and was not optimised. On
  a real corpus, chunking is likely a comparable lever to the ones
  tested here.
- Single language. A multilingual corpus would likely widen the gap
  between dense-only and hybrid.
- The judge is an LLM, not a human panel, and it never sees the corpus.
- Two judging passes measure repeatability, not accuracy. No answer has
  been hand-graded against the corpus.

## Stack

Python, Qdrant (self-hosted), BGE-M3 embeddings, BGE reranker,
Anthropic API. Everything runs locally, which also means the corpus
never leaves the machine — relevant when the real corpus is customer
conversations under GDPR.
