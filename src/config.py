"""Shared configuration, read once from the environment.

Everything that must stay identical across the three retrieval
configurations lives here. If a value can vary between runs, the
experiment is no longer isolating retrieval — so these are read from
`.env` and then written into every run artefact, rather than being
passed around as arguments that a caller could quietly change.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "data" / "corpus"
TESTSET = ROOT / "data" / "testset.json"
REPORTS_RUNS = ROOT / "reports" / "runs"
REPORTS_TMP = ROOT / "reports" / "tmp"

load_dotenv(ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "lumen_spa")

# qdrant-client defaults to a 5 second REST timeout. That is not enough
# here: encoding 18 documents with BGE-M3 saturates the CPU, and the
# create_collection call issued straight afterwards timed out on the
# client while succeeding on the server — which leaves a collection
# behind and reports failure, the worst of both.
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "60"))

# Named vectors in the collection. Both are stored on every point.
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "claude-haiku-4-5-20251001")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-opus-5")

TOP_K = int(os.getenv("TOP_K", "3"))
CANDIDATE_K = int(os.getenv("CANDIDATE_K", "20"))

_threshold = os.getenv("SCORE_THRESHOLD", "").strip()
SCORE_THRESHOLD = float(_threshold) if _threshold else None

# BGE-M3 dense output width. Asserted against the model at ingest time
# rather than trusted, since a mismatch would create a collection that
# silently rejects every upsert.
DENSE_DIM = 1024
