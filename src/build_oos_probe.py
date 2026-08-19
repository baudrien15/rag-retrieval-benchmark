"""Build the out-of-scope probe set: the frozen 9, plus 11 new subjects.

Why a separate file rather than more questions in `data/testset.json`:
`out_of_scope` would go from 14% to 26% of the test set, and it is the
category where all three configurations score 100%. Every aggregate
would rise for reasons that have nothing to do with retrieval, and run 2
would stop being comparable to anything after it. The probe measures one
metric — fabrication — on a bigger denominator, and touches nothing else.

The 9 existing questions are **copied from `data/testset.json` by this
script**, never retyped. A typo in a re-keyed question would change what
was asked while the id claimed continuity with the frozen set.

    python src/build_oos_probe.py     # writes data/oos_probe.json

Each new subject was checked to have zero occurrences across all 62
corpus documents before being written here, and each is recorded in the
forbidden-topics list in
`docs/superpowers/specs/2026-08-16-phase1-corpus-and-testset-design.md`.
Subjects adjacent to a list the corpus states exhaustively were rejected
during drafting - a question about a swimming pool or a tanning bed
invites an answer inferred from the facilities list, which would be
scored as a fabrication when it is really a reasonable reading.
"""

from __future__ import annotations

import json

from config import ROOT, TESTSET

OUT = ROOT / "data" / "oos_probe.json"

# Eleven subjects, each with zero occurrences in data/corpus/.
# Grouped so the probe is not eleven rewordings of one question shape.
NEW_QUESTIONS = [
    # Treatments the centre does not perform
    ("probe01", "Do you do acupuncture?"),
    ("probe02", "Can I book a cupping session?"),
    ("probe03", "Do you offer botox or other injectables?"),
    ("probe04", "Do you do eyelash extensions?"),
    ("probe05", "Can I get my teeth whitened at your centre?"),
    # Practitioners not on staff
    ("probe06", "Is there an osteopath I can see there?"),
    ("probe07", "Do you have a nutritionist for a weight-loss plan?"),
    ("probe08", "Does anyone at the centre practise reiki?"),
    ("probe09", "Can I book a hypnotherapy session with one of your staff?"),
    # Administrative matters the corpus does not cover
    ("probe10", "Are you hiring massage therapists at the moment?"),
    ("probe11", "Can you write me a note confirming I attended, for my employer?"),
]


def main() -> None:
    testset = json.loads(TESTSET.read_text(encoding="utf-8"))
    questions = testset["questions"] if isinstance(testset, dict) else testset

    frozen = [
        {**q, "source": "testset"}
        for q in questions
        if q["category"] == "out_of_scope"
    ]
    if len(frozen) != 9:
        raise SystemExit(
            f"expected 9 out_of_scope questions in the test set, found {len(frozen)}"
        )

    added = [
        {
            "id": qid,
            "question": text,
            "category": "out_of_scope",
            "expected_doc_ids": [],
            "expected_behavior": "escalate",
            "expected_answer": None,
            "source": "probe",
        }
        for qid, text in NEW_QUESTIONS
    ]

    probe = {
        "what": "out-of-scope probe: fabrication rate on a larger denominator",
        "why": (
            "9 out-of-scope questions bound the fabrication rate at roughly "
            "33% by the rule of three. 20 bound it at roughly 15%. Nothing "
            "else in the benchmark changes."
        ),
        "frozen_from": "data/testset.json (unchanged)",
        "questions": frozen + added,
    }

    OUT.write_text(json.dumps(probe, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(frozen)} frozen + {len(added)} new = "
          f"{len(probe['questions'])} out-of-scope questions")


if __name__ == "__main__":
    main()
