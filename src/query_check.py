"""Manual sanity check on the ingested collection. Phase 2's exit test.

This is NOT the measurement. It runs four representative questions —
one per category — and prints what each retrieval method returns, so a
human can look at it and say "yes, that is sensible" before phase 3
starts producing numbers.

Deliberately not scored: an aggregate over four questions would invite
reading it as a result, and the real measurement runs all 30 under
controlled conditions.

    python src/query_check.py                  # the four sample questions
    python src/query_check.py "your question"  # anything you like
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import TESTSET, TOP_K
from retrieval import client, search_dense, search_hybrid, search_sparse

# One per category. q01 is the case the whole benchmark is built around:
# an exact price that lives in one of three near-identical price lists,
# while a treatment description discusses the same treatment at length.
SAMPLE_IDS = ["q01", "q17", "q23", "q27"]


def show(label: str, hits, expected: set[str]) -> None:
    print(f"  {label:8}", end="")
    if not hits:
        print("(nothing returned)")
        return
    parts = []
    for hit in hits:
        mark = "*" if hit.doc_id in expected else " "
        parts.append(f"{mark}{hit.doc_id} ({hit.score:.4f})")
    print("  ".join(parts))


def run(question: str, expected: set[str] | None, category: str = "") -> None:
    """expected=None means an ad-hoc query with no annotation, which is
    not the same thing as an out_of_scope question whose annotation says
    no document should match."""
    qc = client()
    expected = expected if expected is not None else set()
    header = f"{question}"
    if category:
        header += f"   [{category}]"
    print(f"\n{header}")
    if expected:
        print(f"  expected: {', '.join(sorted(expected))}   (* marks an expected doc)")
    elif category == "out_of_scope":
        print("  expected: no document - correct behaviour is escalation")
    else:
        print("  ad-hoc query, no annotation")
    show("dense", search_dense(question, TOP_K, qc), expected)
    show("sparse", search_sparse(question, TOP_K, qc), expected)
    show("hybrid", search_hybrid(question, TOP_K, qc=qc), expected)


def main() -> int:
    if len(sys.argv) > 1:
        run(" ".join(sys.argv[1:]), None)
        return 0

    questions = {
        q["id"]: q
        for q in json.loads(TESTSET.read_text(encoding="utf-8"))["questions"]
    }
    for qid in SAMPLE_IDS:
        q = questions[qid]
        run(q["question"], set(q["expected_doc_ids"]), q["category"])

    print(
        "\nScores are not comparable across methods: dense returns cosine "
        "similarity, hybrid returns an RRF score."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
