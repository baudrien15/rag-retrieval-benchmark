"""Consistency check between the corpus and the test set.

The doc_id is the ground truth key. If a corpus file is renamed and the
test set is not updated, nothing fails loudly — hit@3 simply drops and
the report lies. This script makes that failure loud.

Standard library only. Run from the repository root:

    python src/validate_testset.py

Exit code 1 on any violation, so it can gate a commit hook or CI later.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "data" / "corpus"
TESTSET = ROOT / "data" / "testset.json"

EXPECTED_CATEGORY_COUNTS = {
    "exact_term": 30,
    "semantic": 15,
    "multi_fact": 12,
    "out_of_scope": 9,
}

EXPECTED_DOC_COUNT = 62

# Subjects the corpus must never cover. Each one backs an out_of_scope
# question: if a document starts covering it, that question stops being
# out of scope and its annotation becomes false.
#
# Matching is deliberately crude and case-insensitive. A hit is a prompt
# to go and read the document, not proof of a problem.
FORBIDDEN_TERMS = {
    "laser hair removal": ["laser"],
    "insurance / reimbursement": ["insurance", "reimburse", "mutuelle"],
    "a second location": ["branch", "our other", "only location", "franchise"],
    "corporate invoicing": ["invoice", "purchase order"],
    # "shop" alone matches "bookshop" next door, so match the possessive forms
    "retail sale of products": ["retail", "for sale", "buy the", "our shop", "gift shop"],
    # Added with the phase 1b expansion, for q61-q63.
    "nail treatments": ["manicure", "pedicure", "nail bar"],
    "accommodation": ["overnight stay", "guest room", "bed and breakfast"],
    "treatments at the customer's home": ["home visit", "we come to you", "in your home"],
}


def fail(problems: list[str], message: str) -> None:
    problems.append(message)


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []

    if not TESTSET.exists():
        print(f"FAIL  {TESTSET} does not exist")
        return 1

    raw = TESTSET.read_text(encoding="utf-8")
    testset = json.loads(raw)

    if "_schema" in testset:
        fail(problems, "testset.json still contains the _schema placeholder key")

    # Scan the raw text, not just the expected_answer fields: a
    # PLACEHOLDER left in a question, a doc_id, or a key we do not read
    # would otherwise pass unnoticed.
    if "PLACEHOLDER" in raw:
        fail(problems, "testset.json still contains the string PLACEHOLDER")
    for path in sorted(CORPUS_DIR.glob("*.md")):
        if "PLACEHOLDER" in path.read_text(encoding="utf-8"):
            fail(problems, f"{path.name} still contains the string PLACEHOLDER")

    questions = testset.get("questions", [])
    corpus_ids = {p.stem for p in CORPUS_DIR.glob("*.md")}

    # Unique ids, checked before the ordering rule below, because
    # "ids are not q01..qNN in order" is a confusing way to report a
    # duplicate.
    seen_ids = Counter(q.get("id") for q in questions)
    for qid, count in sorted(seen_ids.items()):
        if count > 1:
            fail(problems, f"question id {qid!r} appears {count} times")

    # 1. Corpus size
    if len(corpus_ids) != EXPECTED_DOC_COUNT:
        fail(
            problems,
            f"corpus holds {len(corpus_ids)} documents, expected {EXPECTED_DOC_COUNT}",
        )

    # 2. Question count and id order
    if len(questions) != sum(EXPECTED_CATEGORY_COUNTS.values()):
        fail(problems, f"testset holds {len(questions)} questions, expected 30")

    expected_ids = [f"q{i:02d}" for i in range(1, len(questions) + 1)]
    actual_ids = [q.get("id") for q in questions]
    if actual_ids != expected_ids:
        fail(problems, "question ids are not q01..qNN in order (order must be fixed)")

    # 3. Category split
    counts = Counter(q.get("category") for q in questions)
    for category, expected in EXPECTED_CATEGORY_COUNTS.items():
        if counts.get(category, 0) != expected:
            fail(
                problems,
                f"category {category}: {counts.get(category, 0)} questions, expected {expected}",
            )
    for category in counts:
        if category not in EXPECTED_CATEGORY_COUNTS:
            fail(problems, f"unknown category {category!r}")

    # 4. Per-question annotation rules
    referenced: set[str] = set()
    for q in questions:
        qid = q.get("id", "<no id>")
        category = q.get("category")
        doc_ids = q.get("expected_doc_ids", [])
        behavior = q.get("expected_behavior")
        answer = q.get("expected_answer")

        for doc_id in doc_ids:
            referenced.add(doc_id)
            if doc_id not in corpus_ids:
                fail(problems, f"{qid} references unknown doc_id {doc_id!r}")

        if len(set(doc_ids)) != len(doc_ids):
            fail(problems, f"{qid} lists the same doc_id twice")

        if category == "out_of_scope":
            if doc_ids:
                fail(problems, f"{qid} is out_of_scope but has expected_doc_ids")
            if behavior != "escalate":
                fail(problems, f"{qid} is out_of_scope but expects {behavior!r}")
            if answer is not None:
                fail(problems, f"{qid} is out_of_scope but has an expected_answer")
        else:
            if not doc_ids:
                fail(problems, f"{qid} is {category} but has no expected_doc_ids")
            if behavior != "answer":
                fail(problems, f"{qid} is {category} but expects {behavior!r}")
            if not answer:
                fail(problems, f"{qid} is {category} but has no expected_answer")
            if answer and "PLACEHOLDER" in answer:
                fail(problems, f"{qid} still has a PLACEHOLDER answer")

        if category == "multi_fact" and len(doc_ids) != 2:
            fail(
                problems,
                f"{qid} is multi_fact with {len(doc_ids)} documents, expected exactly 2",
            )
        if category in ("exact_term", "semantic") and len(doc_ids) != 1:
            fail(
                problems,
                f"{qid} is {category} with {len(doc_ids)} documents, expected exactly 1",
            )

    # 5. Corpus documents no question reaches. Not an error - a corpus is
    #    allowed to be larger than the questions asked of it - but worth
    #    seeing, since an unreachable document only ever acts as a distractor.
    unreferenced = sorted(corpus_ids - referenced)
    if unreferenced:
        warnings.append(
            "documents no question points at (distractors only): "
            + ", ".join(unreferenced)
        )

    # 6. Forbidden subjects
    for path in sorted(CORPUS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").lower()
        for subject, terms in FORBIDDEN_TERMS.items():
            for term in terms:
                if term in text:
                    warnings.append(
                        f"{path.name} contains {term!r} - check it does not cover "
                        f"{subject}, which must stay out of scope"
                    )

    for warning in warnings:
        print(f"WARN  {warning}")
    for problem in problems:
        print(f"FAIL  {problem}")

    if problems:
        print(f"\n{len(problems)} problem(s). Phase 1 is not consistent.")
        return 1

    print(
        f"\nOK  {len(corpus_ids)} documents, {len(questions)} questions, "
        f"every expected_doc_id resolves."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
