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
exact terms), and 30 questions annotated with the documents that should
answer them, split into four categories: exact-term lookup, semantic
paraphrase, multi-document, and out-of-scope.

Three configurations are compared:

| ID | Retrieval |
|----|-----------|
| `dense` | Dense vector search only |
| `hybrid` | Dense + sparse, fused with RRF |
| `hybrid_rerank` | Dense + sparse + reranking |

Three metrics: `hit@3`, judged answer correctness, and fabrication rate
on out-of-scope questions.

### Controlling for the model

The generation model is **deliberately modest and held constant** across
all three runs. A stronger model compensates for poor retrieval by
inferring around gaps, which compresses the difference between
configurations and would make the comparison meaningless. The reported
delta therefore reflects retrieval quality, not model quality.

The judge is a different model from the generator, since models tend to
favour their own output.

## Results

_Pending first run. See `RESULTS.md` for the run log._

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
