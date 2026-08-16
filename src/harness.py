"""Run all 30 questions across all 3 retrieval configurations.

    python src/harness.py                    # all three configs
    python src/harness.py --config dense     # one config
    python src/harness.py --tmp              # write to reports/tmp/ instead

Question order is fixed, taken from data/testset.json as written. The
configurations run in a fixed order too. Nothing here varies between
runs except the retrieval method.

Every run writes one self-describing artefact per configuration to
reports/runs/, carrying the run id, timestamp, git commit, the exact
model identifiers, and the retrieval parameters. A results file that
cannot be tied back to the configuration that produced it proves
nothing, so the header is written before the questions are answered.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CANDIDATE_K,
    COLLECTION,
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    JUDGE_MODEL,
    REPORTS_RUNS,
    REPORTS_TMP,
    RERANKER_MODEL,
    SCORE_THRESHOLD,
    TESTSET,
    TOP_K,
)
from generation import GENERATION_PARAMS, JUDGE_PARAMS, generate, judge
from retrieval import CONFIGS, client

CATEGORIES = ["exact_term", "semantic", "multi_fact", "out_of_scope"]


def git_commit() -> str:
    """The commit the run was produced from. Without it an artefact
    cannot be tied to the corpus and code that made it."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{sha}-dirty" if dirty else sha
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def header(run_id: str, config: str) -> dict:
    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "retrieval_config": config,
        "models": {
            "generation": GENERATION_MODEL,
            "judge": JUDGE_MODEL,
            "embedding": EMBEDDING_MODEL,
            "reranker": RERANKER_MODEL if config == "hybrid_rerank" else None,
        },
        "generation_params": GENERATION_PARAMS,
        # The judge cannot run at temperature 0 - Claude Opus 5 rejects
        # the parameter. Recorded verbatim so a reader sees what was
        # actually sent rather than what CLAUDE.md asked for.
        "judge_params": JUDGE_PARAMS,
        "retrieval": {
            "collection": COLLECTION,
            "top_k": TOP_K,
            "candidate_k": CANDIDATE_K,
            "score_threshold": SCORE_THRESHOLD,
        },
    }


def score(records: list[dict]) -> dict:
    """hit@3, answer_correct, and fabrication_rate, per category."""
    per_category: dict[str, dict] = {}
    for category in CATEGORIES:
        rows = [r for r in records if r["category"] == category]
        if not rows:
            continue
        answerable = [r for r in rows if r["expected_doc_ids"]]
        summary = {
            "n": len(rows),
            "answer_correct": sum(r["correct"] for r in rows) / len(rows),
        }
        # hit@3 is undefined where no document is correct, so it is
        # reported only for the categories that have one.
        if answerable:
            summary["hit_at_3"] = sum(r["hit"] for r in answerable) / len(answerable)
        if category == "out_of_scope":
            summary["fabrication_rate"] = (
                sum(not r["escalated"] for r in rows) / len(rows)
            )
        per_category[category] = summary

    answerable = [r for r in records if r["expected_doc_ids"]]
    oos = [r for r in records if r["category"] == "out_of_scope"]
    return {
        "overall": {
            "hit_at_3": sum(r["hit"] for r in answerable) / len(answerable),
            "answer_correct": sum(r["correct"] for r in records) / len(records),
            "fabrication_rate": sum(not r["escalated"] for r in oos) / len(oos),
        },
        "per_category": per_category,
    }


def run_config(config: str, questions: list[dict], run_id: str, out_dir: Path) -> dict:
    search = CONFIGS[config]
    qc = client()
    records = []

    print(f"\n=== {config} ===")
    for q in questions:
        hits = search(q["question"], TOP_K, qc=qc)
        retrieved = [h.doc_id for h in hits]
        expected = set(q["expected_doc_ids"])
        answer = generate(q["question"], hits)
        verdict = judge(q["question"], q["expected_answer"], answer)

        records.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "expected_doc_ids": q["expected_doc_ids"],
            "expected_answer": q["expected_answer"],
            "retrieved_doc_ids": retrieved,
            "retrieval_scores": [h.score for h in hits],
            "hit": bool(expected & set(retrieved)),
            "answer": answer,
            "correct": bool(verdict["correct"]),
            "escalated": bool(verdict["escalated"]),
            "judge_reason": verdict["reason"],
            "judge_refused": verdict.get("judge_refused", False),
        })
        mark = "OK  " if records[-1]["correct"] else "MISS"
        print(f"  {mark} {q['id']} [{q['category']}] {retrieved}")

    metrics = score(records)
    artefact = {**header(run_id, config), "metrics": metrics, "questions": records}
    path = out_dir / f"{run_id}-{config}.json"
    path.write_text(json.dumps(artefact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {path.relative_to(Path.cwd())}")
    return {"config": config, "metrics": metrics, "artefact": path.name}


def print_table(results: list[dict]) -> None:
    print("\n| Config | hit@3 | Answer correct | Fabrication (OOS) | Artefact |")
    print("|--------|-------|----------------|-------------------|----------|")
    for r in results:
        o = r["metrics"]["overall"]
        print(
            f"| {r['config']} | {o['hit_at_3']:.0%} | {o['answer_correct']:.0%} "
            f"| {o['fabrication_rate']:.0%} | `runs/{r['artefact']}` |"
        )

    print("\nPer category (answer correct):")
    print("\n| Config | " + " | ".join(CATEGORIES) + " | Artefact |")
    print("|--------|" + "|".join("-------" for _ in CATEGORIES) + "|----------|")
    for r in results:
        cells = []
        for category in CATEGORIES:
            summary = r["metrics"]["per_category"].get(category)
            cells.append(f"{summary['answer_correct']:.0%}" if summary else "-")
        print(f"| {r['config']} | " + " | ".join(cells) + f" | `runs/{r['artefact']}` |")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=list(CONFIGS), action="append")
    parser.add_argument("--tmp", action="store_true",
                        help="write to reports/tmp/ (gitignored) instead of reports/runs/")
    args = parser.parse_args()

    questions = json.loads(TESTSET.read_text(encoding="utf-8"))["questions"]
    configs = args.config or list(CONFIGS)
    out_dir = REPORTS_TMP if args.tmp else REPORTS_RUNS
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")

    print(f"run {run_id}: {len(questions)} questions x {len(configs)} configs")
    print(f"generation={GENERATION_MODEL}  judge={JUDGE_MODEL}")

    results = [run_config(c, questions, run_id, out_dir) for c in configs]
    print_table(results)

    print("\nPaste the tables above into RESULTS.md. Every row already "
          "cites its artefact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
