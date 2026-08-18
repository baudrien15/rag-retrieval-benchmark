"""Re-judge every stored answer and measure judge self-agreement.

The judge cannot run at temperature 0 - Claude Opus 5 rejects the
parameter - so its stability is an empirical question, not something the
configuration guarantees. This script answers it.

It is a pure replay: the answers are read from the run artefacts, so no
question is regenerated and no retrieval happens. Only the judge runs
again, on exactly the same inputs it saw the first time.

    python src/judge_stability.py reports/tmp/*.json

A disagreement rate that is not far below the differences between
configurations means those differences are instrument noise.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generation import judge


def main(paths: list[str]) -> int:
    rows = []
    for path in paths:
        artefact = json.loads(Path(path).read_text(encoding="utf-8"))
        config = artefact["retrieval_config"]
        for q in artefact["questions"]:
            second = judge(q["question"], q["expected_answer"], q["answer"])
            rows.append({
                "config": config,
                "id": q["id"],
                "category": q["category"],
                "first_correct": q["correct"],
                "second_correct": bool(second["correct"]),
                "first_escalated": q["escalated"],
                "second_escalated": bool(second["escalated"]),
                "answer": q["answer"],
                "first_reason": q["judge_reason"],
                "second_reason": second["reason"],
            })
            agree = rows[-1]["first_correct"] == rows[-1]["second_correct"]
            print(f"  {'agree ' if agree else 'DIFFER'} {config:14s} {q['id']}")

    n = len(rows)
    agree_correct = sum(r["first_correct"] == r["second_correct"] for r in rows)
    agree_escalated = sum(r["first_escalated"] == r["second_escalated"] for r in rows)
    both = sum(
        r["first_correct"] == r["second_correct"]
        and r["first_escalated"] == r["second_escalated"]
        for r in rows
    )

    print(f"\njudgements replayed: {n}")
    print(f"  correct   agreement: {agree_correct}/{n} = {agree_correct / n:.1%}")
    print(f"  escalated agreement: {agree_escalated}/{n} = {agree_escalated / n:.1%}")
    print(f"  both fields agree:   {both}/{n} = {both / n:.1%}")

    flips = [r for r in rows if r["first_correct"] != r["second_correct"]]
    if flips:
        print(f"\n{len(flips)} verdict flip(s) on `correct`:")
        for r in flips:
            print(f"  {r['config']} {r['id']} [{r['category']}] "
                  f"{r['first_correct']} -> {r['second_correct']}")
            print(f"    1st: {r['first_reason']}")
            print(f"    2nd: {r['second_reason']}")
        print("\nby category:", dict(Counter(r["category"] for r in flips)))
    else:
        print("\nno verdict flips.")

    out = Path("reports/tmp/judge_stability.json")
    out.write_text(json.dumps({
        "judgements": n,
        "correct_agreement": agree_correct / n,
        "escalated_agreement": agree_escalated / n,
        "both_agreement": both / n,
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
