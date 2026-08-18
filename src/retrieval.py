"""The three retrieval configurations under test.

Fusion is done server-side by Qdrant rather than in Python. That matters
for the experiment: RRF implemented by hand is one more thing that could
differ from the reference behaviour, and the point is to compare
retrieval methods, not my arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient, models

from config import (
    CANDIDATE_K,
    COLLECTION,
    DENSE_VECTOR,
    QDRANT_TIMEOUT,
    QDRANT_URL,
    RERANKER_MODEL,
    SPARSE_VECTOR,
    TOP_K,
)
from embeddings import encode_one


@dataclass(frozen=True)
class Hit:
    doc_id: str
    score: float
    text: str


def client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, timeout=QDRANT_TIMEOUT)


def _to_hits(response) -> list[Hit]:
    return [
        Hit(
            doc_id=point.payload["doc_id"],
            score=point.score,
            text=point.payload["text"],
        )
        for point in response.points
    ]


def search_dense(question: str, limit: int = TOP_K, qc: QdrantClient | None = None) -> list[Hit]:
    """Dense vector search only."""
    dense, _ = encode_one(question)
    qc = qc or client()
    return _to_hits(
        qc.query_points(
            collection_name=COLLECTION,
            query=dense,
            using=DENSE_VECTOR,
            limit=limit,
            with_payload=True,
        )
    )


def search_sparse(question: str, limit: int = TOP_K, qc: QdrantClient | None = None) -> list[Hit]:
    """Sparse (lexical) search only. Not one of the three configurations
    under test — kept because it is the only way to see what the sparse
    side actually contributes when a hybrid result looks surprising."""
    _, sparse = encode_one(question)
    qc = qc or client()
    return _to_hits(
        qc.query_points(
            collection_name=COLLECTION,
            query=sparse,
            using=SPARSE_VECTOR,
            limit=limit,
            with_payload=True,
        )
    )


def search_hybrid(
    question: str,
    limit: int = TOP_K,
    candidates: int = CANDIDATE_K,
    qc: QdrantClient | None = None,
) -> list[Hit]:
    """Dense + sparse, fused with reciprocal rank fusion.

    Each branch retrieves `candidates` before fusion. The fused score is
    an RRF score, not a similarity — it is not comparable to the scores
    returned by search_dense, and the phase 4 threshold will have to be
    chosen per configuration for that reason.
    """
    dense, sparse = encode_one(question)
    qc = qc or client()
    return _to_hits(
        qc.query_points(
            collection_name=COLLECTION,
            prefetch=[
                models.Prefetch(query=dense, using=DENSE_VECTOR, limit=candidates),
                models.Prefetch(query=sparse, using=SPARSE_VECTOR, limit=candidates),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
    )


@lru_cache(maxsize=1)
def _reranker():
    """The cross-encoder, loaded straight from transformers.

    FlagEmbedding's FlagReranker cannot be used here: it reaches for the
    slow tokenizer's `prepare_for_model`, which transformers 5 removed,
    and so raises AttributeError on every call. The model is unchanged —
    BAAI/bge-reranker-v2-m3, the one CLAUDE.md specifies — and only the
    loading path differs. Embeddings still go through FlagEmbedding,
    which works fine on transformers 5.
    """
    import torch  # noqa: F401 - imported here to keep the cost off import time
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(RERANKER_MODEL)
    # eval mode and float32, for the same reason the embedder skips fp16:
    # same pair in, same score out, every run.
    model = AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL).eval()
    return tokenizer, model


def _rerank_scores(pairs: list[tuple[str, str]]) -> list[float]:
    """Raw cross-encoder logits, one per (question, document) pair.

    Left unnormalised, which is what FlagReranker returned by default. A
    sigmoid would change the numbers written to the artefact but not the
    ranking, so it would buy nothing here.
    """
    import torch

    tokenizer, model = _reranker()
    with torch.no_grad():
        batch = tokenizer(
            [question for question, _ in pairs],
            [document for _, document in pairs],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        return model(**batch).logits.view(-1).float().tolist()


def search_hybrid_rerank(
    question: str,
    limit: int = TOP_K,
    candidates: int = CANDIDATE_K,
    qc: QdrantClient | None = None,
) -> list[Hit]:
    """Dense + sparse fused with RRF, then the fused candidates reranked.

    The reranker sees the RRF-fused candidate list, not the two branches
    separately. That is what makes this configuration a strict addition
    to `hybrid` rather than a third, different pipeline: the only change
    is that the top `limit` are chosen by a cross-encoder instead of by
    the fusion score.

    The returned score is a reranker score, comparable to neither the
    cosine similarity of `dense` nor the RRF score of `hybrid`.
    """
    fused = search_hybrid(question, limit=candidates, candidates=candidates, qc=qc)
    if not fused:
        return []

    scores = _rerank_scores([(question, hit.text) for hit in fused])

    ranked = sorted(
        (Hit(doc_id=hit.doc_id, score=float(score), text=hit.text)
         for hit, score in zip(fused, scores)),
        key=lambda hit: hit.score,
        reverse=True,
    )
    return ranked[:limit]


# The three configurations under test, by the ids used in RESULTS.md.
CONFIGS = {
    "dense": search_dense,
    "hybrid": search_hybrid,
    "hybrid_rerank": search_hybrid_rerank,
}
