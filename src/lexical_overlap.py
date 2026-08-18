"""Measure how much of each question's vocabulary is lifted verbatim
from the document it is annotated against.

Why this exists. A question written while reading its source document
imports that document's wording - exact treatment names, exact phrasing.
Exact lexical match is what sparse retrieval is good at and what dense
retrieval is bad at, so questions written that way structurally favour
the hybrid configurations. That is a confound pointing in the same
direction as the result this benchmark expects to find, which is the
worst direction for a confound to point.

The original thirty questions were written before their documents. The
thirty-five added with the corpus expansion were written while reading
them. If the second group shows materially higher overlap, the headline
number is inflated and the questions have to be rephrased.

    python src/lexical_overlap.py            # distributions
    python src/lexical_overlap.py --verbose  # every question

Stdlib only, like validate_testset.py: this is a measurement anyone
should be able to reproduce without installing the project.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
TESTSET = ROOT / "data" / "testset.json"

# The original set, written before the corpus documents existed.
ORIGINAL_COUNT = 30

# Function words carry no retrieval signal, so counting them would
# dilute the measure towards a meaningless middle. Deliberately short
# and explicit rather than pulled from a library.
STOPWORDS = {
    "a", "about", "after", "all", "am", "an", "and", "any", "anything",
    "are", "as", "at", "be", "been", "before", "being", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "get", "give",
    "go", "had", "has", "have", "how", "i", "if", "in", "into", "is",
    "it", "its", "just", "like", "long", "many", "me", "much", "my",
    "need", "no", "not", "of", "on", "one", "or", "our", "out", "so",
    "some", "something", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "to", "up", "us", "want", "was", "we",
    "what", "when", "where", "which", "who", "will", "with", "would",
    "you", "your", "d", "ll", "re", "s", "t", "ve",
}

TOKEN = re.compile(r"[a-z0-9]+")


def content_words(text: str) -> list[str]:
    return [w for w in TOKEN.findall(text.lower()) if w not in STOPWORDS]


def overlap(question: str, doc_ids: list[str]) -> tuple[float, list[str], list[str]]:
    """Share of the question's content words appearing verbatim in the
    text of its expected documents. Returns (share, matched, missed)."""
    source = " ".join(
        (CORPUS / f"{doc_id}.md").read_text(encoding="utf-8") for doc_id in doc_ids
    )
    vocabulary = set(content_words(source))
    words = content_words(question)
    if not words:
        return 0.0, [], []
    matched = [w for w in words if w in vocabulary]
    missed = [w for w in words if w not in vocabulary]
    return len(matched) / len(words), matched, missed


def describe(name: str, shares: list[float]) -> None:
    quantiles = statistics.quantiles(shares, n=4) if len(shares) > 3 else [float("nan")] * 3
    print(f"{name:22s} n={len(shares):3d}  "
          f"mean={statistics.mean(shares):.0%}  "
          f"median={statistics.median(shares):.0%}  "
          f"min={min(shares):.0%}  max={max(shares):.0%}  "
          f"p25={quantiles[0]:.0%}  p75={quantiles[2]:.0%}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    questions = json.loads(TESTSET.read_text(encoding="utf-8"))["questions"]

    rows = []
    for index, q in enumerate(questions):
        # out_of_scope questions have no expected document, so there is
        # nothing to overlap with.
        if not q["expected_doc_ids"]:
            continue
        share, matched, missed = overlap(q["question"], q["expected_doc_ids"])
        rows.append({
            "id": q["id"],
            "group": "original" if index < ORIGINAL_COUNT else "added",
            "category": q["category"],
            "question": q["question"],
            "overlap": share,
            "matched": matched,
            "missed": missed,
        })

    original = [r["overlap"] for r in rows if r["group"] == "original"]
    added = [r["overlap"] for r in rows if r["group"] == "added"]

    print("Share of question content words appearing verbatim in the "
          "expected document\n")
    describe("original (q01-q30)", original)
    describe("added (q31-)", added)
    gap = statistics.mean(added) - statistics.mean(original)
    print(f"\ngap in means: {gap:+.1%}")

    if args.verbose:
        print("\nper question, worst first:")
        for r in sorted(rows, key=lambda r: -r["overlap"]):
            print(f"  {r['id']} [{r['group']:8s}] {r['overlap']:5.0%}  {r['question']}")
            if r["missed"]:
                print(f"        not in the document: {', '.join(r['missed'])}")

    out = ROOT / "reports" / "tmp" / "lexical_overlap.json"
    out.write_text(json.dumps({
        "original_mean": statistics.mean(original),
        "added_mean": statistics.mean(added),
        "gap": gap,
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
