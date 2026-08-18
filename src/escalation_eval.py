"""Measure the escalation detector against the judge.

The split is the point of this script. `escalation.is_escalation` was
written while looking at the `dense` artefacts and nothing else. This
evaluates it on the `hybrid` and `hybrid_rerank` artefacts, which were
not opened until the rule was frozen.

Two rates are reported separately and never combined:

  missed escalation   detector False, judge True
                      -> a declined answer served to the customer
  wrong escalation    detector True, judge False
                      -> an answerable question put in front of an agent

An aggregate agreement rate is deliberately not printed. Escalations are
roughly 9 of 66 questions per configuration, so a detector that answered
"False" every time would still score about 86% agreement while missing
every escalation there is. The two rates cannot be averaged into
anything meaningful.

**The split is by configuration, not by question, and that is a weakness
this script measures rather than hides.** Both sets cover the same 66
questions; only the answers differ. Counting artefact rows therefore
overstates the evidence twice over: the same question recurs across
configurations and across the two benchmark runs, and most escalating
questions in the evaluation set had already been seen escalating during
development. So three denominators are printed, not one:

  answers              artefact rows - the loosest count
  distinct questions   how many different questions those rows cover
  unseen escalations   answers to questions that never escalated in the
                       development set - the only genuinely held-out
                       evidence, and by far the smallest number

    python src/escalation_eval.py

Writes the artefact `reports/runs/<timestamp>-escalation-detector.json`
unless `--tmp` is passed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from config import REPORTS_RUNS, REPORTS_TMP, ROOT
from escalation import is_escalation

# The split, by filename. Development artefacts are listed so the
# reader can check that the evaluation set really was held out.
DEVELOPMENT = (
    "2026-08-18T093939Z-dense.json",
    "2026-08-18T083135Z-dense.json",
)
EVALUATION = (
    "2026-08-18T093939Z-hybrid.json",
    "2026-08-18T093939Z-hybrid_rerank.json",
    "2026-08-18T083135Z-hybrid.json",
    "2026-08-18T084052Z-hybrid_rerank.json",
)


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        commit = out.stdout.strip()
        return f"{commit}-dirty" if dirty.stdout.strip() else commit
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def score(filenames) -> dict:
    """Run the detector over a set of artefacts and collect disagreements."""
    rows, missed, wrong = [], [], []

    for name in filenames:
        path = REPORTS_RUNS / name
        run = json.loads(path.read_text(encoding="utf-8"))
        for q in run["questions"]:
            detected = is_escalation(q["answer"])
            judged = bool(q["escalated"])
            row = {
                "artefact": name,
                "config": run["retrieval_config"],
                "id": q["id"],
                "category": q["category"],
                "detector": detected,
                "judge": judged,
                "answer": q["answer"],
            }
            rows.append(row)
            if judged and not detected:
                missed.append(row)
            elif detected and not judged:
                wrong.append(row)

    judge_escalations = sum(r["judge"] for r in rows)
    judge_answers = len(rows) - judge_escalations

    return {
        "artefacts": list(filenames),
        # Kept for cross-set analysis; stripped before the artefact is
        # written, since the source artefacts are committed already.
        "rows": rows,
        "escalating_question_ids": {r["id"] for r in rows if r["judge"]},
        "answers": len(rows),
        "distinct_questions": len({r["id"] for r in rows}),
        "judge_escalations": judge_escalations,
        "judge_escalation_questions": len({r["id"] for r in rows if r["judge"]}),
        "judge_answers": judge_answers,
        "judge_answer_questions": len({r["id"] for r in rows if not r["judge"]}),
        "missed_escalations": {
            "count": len(missed),
            "of": judge_escalations,
            "rate": (len(missed) / judge_escalations) if judge_escalations else None,
            "cases": missed,
        },
        "wrong_escalations": {
            "count": len(wrong),
            "of": judge_answers,
            "rate": (len(wrong) / judge_answers) if judge_answers else None,
            "cases": wrong,
        },
    }


def unseen_escalations(development: dict, evaluation: dict) -> dict:
    """Evaluation answers to questions that never escalated in development.

    This is the only part of the evaluation set the rule cannot have been
    fitted to. Everything else is a question whose declination phrasing
    was visible while the patterns were being written, in a different
    configuration's answer to the same question.
    """
    seen = {
        case["id"]
        for case in development["missed_escalations"]["cases"]
        + development["wrong_escalations"]["cases"]
    }
    # The development set's escalating questions, from its full rows.
    seen |= development["escalating_question_ids"]

    cases = [
        row for row in evaluation["rows"]
        if row["judge"] and row["id"] not in seen
    ]
    caught = [row for row in cases if row["detector"]]

    return {
        "definition": "evaluation answers whose question never escalated in the development set",
        "answers": len(cases),
        "distinct_questions": len({row["id"] for row in cases}),
        "caught": len(caught),
        "missed": len(cases) - len(caught),
        "cases": cases,
    }


def report(title: str, result: dict) -> None:
    print(f"\n{title}")
    print(f"  artefacts: {', '.join(result['artefacts'])}")
    print(f"  {result['answers']} answers over "
          f"{result['distinct_questions']} distinct questions")
    print(f"  {result['judge_escalations']} judged escalations "
          f"(over {result['judge_escalation_questions']} distinct questions), "
          f"{result['judge_answers']} judged answers "
          f"(over {result['judge_answer_questions']} distinct questions)")

    missed = result["missed_escalations"]
    wrong = result["wrong_escalations"]
    print(f"  missed escalations : {missed['count']}/{missed['of']}"
          f"   (detector False, judge True)")
    print(f"  wrong escalations  : {wrong['count']}/{wrong['of']}"
          f"   (detector True, judge False)")

    for label, bucket in (("MISSED", missed), ("WRONG", wrong)):
        for case in bucket["cases"]:
            print(f"    {label} {case['id']} [{case['config']}, {case['category']}]")
            print(f"      {case['answer'][:200]!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tmp", action="store_true",
                        help="write to reports/tmp/ instead of reports/runs/")
    args = parser.parse_args()

    development = score(DEVELOPMENT)
    evaluation = score(EVALUATION)
    unseen = unseen_escalations(development, evaluation)

    report("DEVELOPMENT SET (the rule was written on these)", development)
    report("EVALUATION SET (a different configuration, the same questions)", evaluation)

    overlap = development["escalating_question_ids"] | evaluation["escalating_question_ids"]
    shared_questions = {r["id"] for r in development["rows"]} & {
        r["id"] for r in evaluation["rows"]
    }
    print(f"\nSPLIT WEAKNESS")
    print(f"  questions common to both sets: {len(shared_questions)} "
          f"- the split is by configuration, not by question")
    print(f"  distinct escalating questions across both sets: {len(overlap)}")

    print(f"\nUNSEEN ESCALATIONS (the only genuinely held-out evidence)")
    print(f"  {unseen['answers']} answers over "
          f"{unseen['distinct_questions']} distinct questions")
    print(f"  caught {unseen['caught']}/{unseen['answers']}, "
          f"missed {unseen['missed']}/{unseen['answers']}")
    for case in unseen["cases"]:
        print(f"    {'CAUGHT' if case['detector'] else 'MISSED'} "
              f"{case['id']} [{case['config']}, {case['category']}]")

    # The rows carry every answer twice over; the source artefacts are
    # committed, so the aggregate plus the disagreement cases is enough.
    for result in (development, evaluation):
        result.pop("rows")
        result["escalating_question_ids"] = sorted(result["escalating_question_ids"])

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    artefact = {
        "run_id": f"{timestamp}-escalation-detector",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "what": "escalation detector agreement with the judge's `escalated` field",
        "detector": "src/escalation.py::is_escalation (pure, no model call)",
        "judge_model": "claude-opus-5",
        "generation_model": "claude-haiku-4-5-20251001",
        "split": {
            "by": "retrieval configuration, not by question",
            "questions_common_to_both_sets": len(shared_questions),
            "caveat": (
                "Both sets cover the same 66 questions. Artefact-row counts "
                "overstate the evidence; the unseen_escalations block below "
                "is the only part the rule cannot have been fitted to."
            ),
        },
        "development": development,
        "evaluation": evaluation,
        "unseen_escalations": unseen,
    }

    out_dir = REPORTS_TMP if args.tmp else REPORTS_RUNS
    out_path = Path(out_dir) / f"{timestamp}-escalation-detector.json"
    out_path.write_text(json.dumps(artefact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
