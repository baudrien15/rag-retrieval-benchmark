"""BGE-M3 encoding: dense and sparse from one model.

BGE-M3 produces both representations in a single forward pass, which is
why it was chosen — the sparse side is not a second model bolted on, so
the two views of a document cannot drift apart.

fastembed does not carry BGE-M3 (checked against fastembed 0.8.0: no
bge-m3 in either TextEmbedding or SparseTextEmbedding), so this goes
through FlagEmbedding, the alternative CLAUDE.md names.

The model is loaded once per process and reused. It is a few seconds of
startup and about 2 GB resident.
"""

from __future__ import annotations

from functools import lru_cache

from qdrant_client import models

from config import DENSE_DIM, EMBEDDING_MODEL


@lru_cache(maxsize=1)
def _model():
    from FlagEmbedding import BGEM3FlagModel

    # use_fp16 is off deliberately. It is a CPU-hostile setting and it
    # costs precision; this project needs the same input to give the
    # same vector on every run more than it needs speed on 18 documents.
    return BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=False)


def _to_sparse_vector(lexical_weights: dict) -> models.SparseVector:
    """Convert BGE-M3 lexical weights to a Qdrant sparse vector.

    FlagEmbedding returns {token_id_as_string: weight}. Qdrant wants
    parallel indices/values lists. Zero-weight tokens are dropped: they
    carry no ranking signal and only inflate the index.
    """
    pairs = sorted(
        (int(token_id), float(weight))
        for token_id, weight in lexical_weights.items()
        if float(weight) > 0.0
    )
    return models.SparseVector(
        indices=[i for i, _ in pairs],
        values=[v for _, v in pairs],
    )


def encode(texts: list[str]) -> list[tuple[list[float], models.SparseVector]]:
    """Encode texts to (dense, sparse) pairs, in input order."""
    out = _model().encode(
        texts,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )

    dense = out["dense_vecs"]
    if dense.shape[1] != DENSE_DIM:
        raise SystemExit(
            f"{EMBEDDING_MODEL} returned {dense.shape[1]}-dim vectors, "
            f"but config.DENSE_DIM is {DENSE_DIM}. The collection would "
            f"reject every upsert."
        )

    return [
        (dense[i].tolist(), _to_sparse_vector(out["lexical_weights"][i]))
        for i in range(len(texts))
    ]


def encode_one(text: str) -> tuple[list[float], models.SparseVector]:
    return encode([text])[0]
