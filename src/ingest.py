"""Build the Qdrant collection and load the corpus into it.

One document is one point. No chunking — the documents were written
short enough for that to be reasonable, and chunking is a second
variable that this experiment deliberately does not touch.

Run from the repository root:

    python src/ingest.py

The collection is recreated from scratch on every run. Ingestion is
cheap (18 documents) and a rebuilt collection is easier to trust than
an incrementally patched one.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qdrant_client import QdrantClient, models

from config import (
    COLLECTION,
    CORPUS_DIR,
    DENSE_DIM,
    DENSE_VECTOR,
    EMBEDDING_MODEL,
    QDRANT_TIMEOUT,
    QDRANT_URL,
    SPARSE_VECTOR,
)
from embeddings import encode


def load_corpus() -> list[tuple[str, str]]:
    """Return (doc_id, text) for every corpus document, in stable order.

    Sorted by doc_id so that point ids are reproducible across runs.
    """
    docs = [
        (path.stem, path.read_text(encoding="utf-8").strip())
        for path in sorted(CORPUS_DIR.glob("*.md"))
    ]
    if not docs:
        raise SystemExit(f"no documents found in {CORPUS_DIR}")
    empty = [doc_id for doc_id, text in docs if not text]
    if empty:
        raise SystemExit(f"empty corpus documents: {', '.join(empty)}")
    return docs


def main() -> int:
    client = QdrantClient(url=QDRANT_URL, timeout=QDRANT_TIMEOUT)
    docs = load_corpus()
    print(f"corpus: {len(docs)} documents")

    print(f"encoding with {EMBEDDING_MODEL} (first run downloads the model)...")
    vectors = encode([text for _, text in docs])

    if client.collection_exists(COLLECTION):
        print(f"dropping existing collection {COLLECTION!r}")
        client.delete_collection(COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            DENSE_VECTOR: models.VectorParams(
                size=DENSE_DIM,
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            SPARSE_VECTOR: models.SparseVectorParams(
                index=models.SparseIndexParams()
            )
        },
    )
    print(f"created collection {COLLECTION!r} with named vectors "
          f"{DENSE_VECTOR!r} (dense, {DENSE_DIM}d, cosine) and "
          f"{SPARSE_VECTOR!r} (sparse)")

    points = [
        models.PointStruct(
            id=index,
            vector={DENSE_VECTOR: dense, SPARSE_VECTOR: sparse},
            payload={"doc_id": doc_id, "text": text},
        )
        for index, ((doc_id, text), (dense, sparse)) in enumerate(zip(docs, vectors))
    ]
    client.upsert(collection_name=COLLECTION, points=points, wait=True)

    count = client.count(COLLECTION, exact=True).count
    print(f"upserted {len(points)} points; collection now holds {count}")

    if count != len(docs):
        print(f"FAIL  expected {len(docs)} points, found {count}")
        return 1

    # The doc_id payload is the ground truth key the whole benchmark is
    # scored against, so confirm it survived the round trip rather than
    # assuming it did.
    stored = {
        record.payload["doc_id"]
        for record in client.scroll(COLLECTION, limit=1000, with_payload=True)[0]
    }
    missing = {doc_id for doc_id, _ in docs} - stored
    if missing:
        print(f"FAIL  doc_ids missing from payloads: {', '.join(sorted(missing))}")
        return 1

    print("OK  every doc_id is retrievable from its payload")
    return 0


if __name__ == "__main__":
    sys.exit(main())
