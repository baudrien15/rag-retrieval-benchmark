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
    from FlagEmbedding import FlagReranker

    # use_fp16 off for the same reason as the embedder: same input, same
    # score, every run.
    return FlagReranker(RERANKER_MODEL, use_fp16=False)


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

    scores = _reranker().compute_score([(question, hit.text) for hit in fused])
    # compute_score returns a bare float when given a single pair.
    if not isinstance(scores, list):
        scores = [scores]

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
