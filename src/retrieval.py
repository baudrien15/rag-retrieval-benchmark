"""The retrieval configurations under test.

`dense` and `hybrid` are implemented here. `hybrid_rerank` belongs to
phase 3, which is where the reranker enters.

Fusion is done server-side by Qdrant rather than in Python. That matters
for the experiment: RRF implemented by hand is one more thing that could
differ from the reference behaviour, and the point is to compare
retrieval methods, not my arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from config import (
    CANDIDATE_K,
    COLLECTION,
    DENSE_VECTOR,
    QDRANT_TIMEOUT,
    QDRANT_URL,
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
