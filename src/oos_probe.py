"""Run the 20-question out-of-scope probe across all three configurations.

    python src/oos_probe.py           # all three configs
    python src/oos_probe.py --tmp     # write to reports/tmp/ instead

**This is not a benchmark run and it does not produce a results table.**
It measures one thing: how often a configuration answers a question the
corpus does not cover, instead of declining. Nothing else here feeds a
published comparison, so the questions can grow without invalidating
run 2.

The reason for it is the weakest number in the repository. Nine
out-of-scope questions with zero fabrications bound the true rate at
roughly 33% by the rule of three. Twenty bound it at roughly 15%. The
observation was never the problem; the denominator was.

`hit@1` and `hit@3` are not computed. Every question here has an empty
`expected_doc_ids`, so retrieval metrics are undefined by construction —
printing a 0% would invite it to be read as a retrieval failure.

Retrieval, generation and judging are the same imports the benchmark
uses, at the same parameters, so a fabrication counted here means the
same thing it means in RESULTS.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    ROOT,
    SCORE_THRESHOLD,
    TOP_K,
)
from escalation import is_escalation
from generation import GENERATION_PARAMS, JUDGE_PARAMS, generate, judge
from retrieval import CONFIGS, client

PROBE = ROOT / "data" / "oos_probe.json"


def git_commit() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{sha}-dirty" if dirty else sha
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def header(run_id: str, config: str) -> dict:
    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "what": "out-of-scope probe - fabrication only, not a benchmark run",
        "retrieval_config": config,
        "collection": COLLECTION,
        "models": {
            "generation": GENERATION_MODEL,
            "judge": JUDGE_MODEL,
            "embedding": EMBEDDING_MODEL,
            "reranker": RERANKER_MODEL,
        },
        "generation_params": GENERATION_PARAMS,
        "judge_params": JUDGE_PARAMS,
        "retrieval": {
            "top_k": TOP_K,
            "candidate_k": CANDIDATE_K,
            "score_threshold": SCORE_THRESHOLD,
        },
        "probe_set": "data/oos_probe.json (9 frozen from data/testset.json + 11 new)",
    }


def run_config(config: str, questions: list[dict], run_id: str, out_dir: Path) -> dict:
    search = CONFIGS[config]
    qc = client()
    records = []

    print(f"\n=== {config} ===")
    for q in questions:
        hits = search(q["question"], TOP_K, qc=qc)
        answer = generate(q["question"], hits)
        verdict = judge(q["question"], q["expected_answer"], answer)
        fabricated = not bool(verdict["escalated"])

        records.append({
            "id": q["id"],
            "source": q["source"],
            "question": q["question"],
            "retrieved_doc_ids": [h.doc_id for h in hits],
            "retrieval_scores": [h.score for h in hits],
            "answer": answer,
            "escalated": bool(verdict["escalated"]),
            "fabricated": fabricated,
            "correct": bool(verdict["correct"]),
            "judge_reason": verdict["reason"],
            # The serving-time detector, recorded alongside the judge so
            # the probe doubles as fresh evidence for it. It is not used
            # to decide anything here.
            "detector_escalated": is_escalation(answer),
        })
        mark = "FABRICATED" if fabricated else "escalated "
        print(f"  {mark} {q['id']:<8} {q['question'][:56]}")

    fabrications = [r for r in records if r["fabricated"]]
    frozen = [r for r in records if r["source"] == "testset"]
    added = [r for r in records if r["source"] == "probe"]
    detector_disagreements = [
        r for r in records if r["detector_escalated"] != r["escalated"]
    ]

    metrics = {
        "questions": len(records),
        "fabrications": len(fabrications),
        "fabricating_question_ids": [r["id"] for r in fabrications],
        "frozen_nine": {
            "questions": len(frozen),
            "fabrications": sum(r["fabricated"] for r in frozen),
        },
        "new_eleven": {
            "questions": len(added),
            "fabrications": sum(r["fabricated"] for r in added),
        },
        "detector_disagreements": [
            {"id": r["id"], "judge": r["escalated"], "detector": r["detector_escalated"]}
            for r in detector_disagreements
        ],
    }

    artefact = {**header(run_id, config), "metrics": metrics, "questions": records}
    path = out_dir / f"{run_id}-{config}-oos-probe.json"
    path.write_text(json.dumps(artefact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {path.name}")
    return {"config": config, "metrics": metrics,
            "artefact": f"{out_dir.name}/{path.name}"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tmp", action="store_true",
                        help="write to reports/tmp/ instead of reports/runs/")
    args = parser.parse_args()

    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    questions = probe["questions"]

    out_dir = REPORTS_TMP if args.tmp else REPORTS_RUNS
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")

    results = [run_config(c, questions, run_id, Path(out_dir)) for c in CONFIGS]

    print("\n| Config | Questions | Fabrications | frozen 9 | new 11 | Artefact |")
    print("|--------|-----------|--------------|----------|--------|----------|")
    for r in results:
        m = r["metrics"]
        print(f"| {r['config']} | {m['questions']} | **{m['fabrications']} / "
              f"{m['questions']}** | {m['frozen_nine']['fabrications']}/9 "
              f"| {m['new_eleven']['fabrications']}/11 | `{r['artefact']}` |")

    total_q = sum(r["metrics"]["questions"] for r in results)
    total_f = sum(r["metrics"]["fabrications"] for r in results)
    print(f"\n{total_f} fabrications over {total_q} out-of-scope questions asked "
          f"({len(results)} configurations x {results[0]['metrics']['questions']}).")
    print("Per configuration the denominator is 20, which by the rule of three "
          "bounds the true rate at roughly 15% at worst.")


if __name__ == "__main__":
    main()
