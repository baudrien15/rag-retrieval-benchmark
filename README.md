# RAG Retrieval Benchmark

Measuring how much retrieval strategy — not prompting — drives answer
quality and hallucination rate in a support chatbot.

> Status: work in progress. Numbers below are placeholders until the
> first full run completes.

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

| Config | hit@1 | hit@3 | Answer correct | Fabrication |
|--------|-------|-------|----------------|-------------|
| `dense` | 88% | 95% | 83% | 0% |
| `hybrid` | 84% | 93% | 85% | 0% |
| **`hybrid_rerank`** | **91%** | **100%** | **89%** | 0% |

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

## Confidence threshold

_Pending._

## Running it

```bash
cp .env.example .env      # add your keys
docker compose up -d      # starts Qdrant locally
pip install -r requirements.txt
```

## Limitations

Stated plainly, because a benchmark that hides its limits is not worth
much:

- Synthetic corpus. Real support corpora are messier, longer, and
  contradict themselves.
- 30 questions is enough to see a direction, not enough for tight
  confidence intervals.
- Chunking is fixed at one document per chunk and was not optimised. On
  a real corpus, chunking is likely a comparable lever to the ones
  tested here.
- Single language. A multilingual corpus would likely widen the gap
  between dense-only and hybrid.
- The judge is an LLM, not a human panel.

## Stack

Python, Qdrant (self-hosted), BGE-M3 embeddings, BGE reranker,
Anthropic API. Everything runs locally, which also means the corpus
never leaves the machine — relevant when the real corpus is customer
conversations under GDPR.
