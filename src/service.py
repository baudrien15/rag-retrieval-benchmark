"""HTTP front end for the n8n workflow demo.

The workflow runs on a remote VPS; the pipeline it drives — Qdrant,
BGE-M3, the reranker — runs on this machine. This service is the only
thing between them, exposed through a cloudflared tunnel while the demo
is being recorded.

**It imports `retrieval` and `generation` unchanged.** That is the whole
point: the demo shows the pipeline the numbers were measured on, not a
reimplementation that drifts from it. Nothing here is a second variable.

Escalation routing uses `escalation.is_escalation`, which reads the
generated answer and does not touch the generator — measured in
`docs/escalation-detector.md`.

    uvicorn service:app --app-dir src --port 8000
    cloudflared tunnel --url http://localhost:8000

Auth: every request must carry the shared secret in `X-Lumen-Secret`.
The tunnel URL is public, so an unauthenticated endpoint here is an
open Anthropic API key with extra steps.
"""

from __future__ import annotations

import hmac
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from config import CANDIDATE_K, GENERATION_MODEL, TOP_K
from escalation import is_escalation
from generation import generate
from retrieval import search_hybrid_rerank

# The demo runs the winning configuration and only that one. Letting the
# request choose would add a branch to the canvas that teaches nothing —
# the comparison is what RESULTS.md is for.
CONFIG_ID = "hybrid_rerank"

SHARED_SECRET = os.getenv("LUMEN_SERVICE_SECRET", "")

app = FastAPI(
    title="Lumen Spa retrieval service",
    description="Serving front end for the n8n workflow demo.",
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None


def _authenticate(supplied: str | None) -> None:
    """Reject anything that does not carry the shared secret.

    Fails closed: with no secret configured the endpoint refuses every
    request rather than serving an open one. `compare_digest` keeps the
    comparison constant-time.
    """
    if not SHARED_SECRET:
        raise HTTPException(
            status_code=503,
            detail="LUMEN_SERVICE_SECRET is not set; refusing to serve unauthenticated.",
        )
    if not supplied or not hmac.compare_digest(supplied, SHARED_SECRET):
        raise HTTPException(status_code=401, detail="bad or missing X-Lumen-Secret")


@app.get("/healthz")
def healthz() -> dict:
    """Liveness only. Deliberately unauthenticated and says nothing."""
    return {"status": "ok"}


@app.post("/answer")
def answer(
    request: AskRequest,
    x_lumen_secret: str | None = Header(default=None),
) -> dict:
    """Retrieve, generate, and decide whether the answer can be served.

    `escalated` is the field the workflow's IF node routes on. It is
    always present and always a boolean — the workflow never has to
    parse prose, and there is no path on which a missing field silently
    becomes "serve it".
    """
    _authenticate(x_lumen_secret)

    hits = search_hybrid_rerank(request.question)
    generated = generate(request.question, hits)
    escalated = is_escalation(generated)

    return {
        "conversation_id": request.conversation_id,
        "question": request.question,
        "config": CONFIG_ID,
        "generation_model": GENERATION_MODEL,
        "top_k": TOP_K,
        "candidate_k": CANDIDATE_K,
        "answer": generated,
        "escalated": escalated,
        # Returned for the demo's benefit: the canvas can show what was
        # retrieved. It is not what the routing reads.
        "retrieved": [
            {"doc_id": hit.doc_id, "score": hit.score} for hit in hits
        ],
    }
