"""Phase 4: do retrieval scores separate in-scope from out-of-scope?

A confidence threshold works by refusing to answer when the best
retrieval score is too low. That is only possible if out-of-scope
questions actually score lower than answerable ones. This script plots
the two distributions and reports how far apart they are.

On this corpus there is nothing for a threshold to cut - fabrication is
already 0% across all three configurations. The question the plot
answers is the transferable one: **would a threshold be workable on a
real corpus**, where the generator is not so well behaved?

The top-1 score is used, because that is what a threshold would actually
test. Scores are NOT comparable between configurations - cosine
similarity, an RRF score and a cross-encoder logit are three different
scales - so each configuration is plotted and analysed on its own axes.

    python src/score_distribution.py                 # all three configs
    python src/score_distribution.py --run <run_id>  # a specific run
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "reports" / "runs"
CONFIGS = ["dense", "hybrid", "hybrid_rerank"]


def load(run_id: str) -> dict[str, dict]:
    out = {}
    for config in CONFIGS:
        path = RUNS / f"{run_id}-{config}.json"
        if path.exists():
            out[config] = json.loads(path.read_text(encoding="utf-8"))
    return out


def split_scores(artefact: dict) -> tuple[list[float], list[float]]:
    """Top-1 retrieval score, split by whether the question is
    answerable from the corpus at all."""
    in_scope, out_of_scope = [], []
    for q in artefact["questions"]:
        if not q["retrieval_scores"]:
            continue
        top = q["retrieval_scores"][0]
        (out_of_scope if q["category"] == "out_of_scope" else in_scope).append(top)
    return in_scope, out_of_scope


def separation(in_scope: list[float], out_of_scope: list[float]) -> dict:
    """How cleanly could a single cutoff divide the two sets?

    Reported as the best achievable split: the threshold that correctly
    refuses the most out-of-scope questions while wrongly refusing the
    fewest answerable ones. If the distributions overlap, no cutoff
    achieves both and the trade-off is the finding.
    """
    best = None
    for candidate in sorted(set(in_scope + out_of_scope)):
        # Refuse anything scoring below the candidate threshold.
        refused_oos = sum(s < candidate for s in out_of_scope)
        lost_in_scope = sum(s < candidate for s in in_scope)
        score = refused_oos / len(out_of_scope) - lost_in_scope / len(in_scope)
        if best is None or score > best["score"]:
            best = {
                "threshold": candidate,
                "score": score,
                "out_of_scope_caught": refused_oos / len(out_of_scope),
                "in_scope_lost": lost_in_scope / len(in_scope),
            }
    return {
        "in_scope_mean": statistics.mean(in_scope),
        "in_scope_min": min(in_scope),
        "out_of_scope_mean": statistics.mean(out_of_scope),
        "out_of_scope_max": max(out_of_scope),
        # A clean gap means every out-of-scope question scored below
        # every answerable one. Anything else means overlap.
        "clean_gap": min(in_scope) > max(out_of_scope),
        "best_cutoff": best,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="2026-08-18T093939Z")
    args = parser.parse_args()

    artefacts = load(args.run)
    if not artefacts:
        print(f"no artefacts found for run {args.run} in {RUNS}")
        return 1

    fig, axes = plt.subplots(1, len(artefacts), figsize=(5 * len(artefacts), 4.2))
    if len(artefacts) == 1:
        axes = [axes]

    summary = {}
    for ax, (config, artefact) in zip(axes, artefacts.items()):
        in_scope, out_of_scope = split_scores(artefact)
        stats = separation(in_scope, out_of_scope)
        summary[config] = stats

        ax.hist([in_scope, out_of_scope], bins=12,
                label=[f"answerable (n={len(in_scope)})",
                       f"out of scope (n={len(out_of_scope)})"],
                color=["#3b6ea5", "#c4553b"])
        cutoff = stats["best_cutoff"]["threshold"]
        ax.axvline(cutoff, color="black", linestyle="--", linewidth=1)
        ax.set_title(f"{config}\nbest cutoff {cutoff:.3g}: catches "
                     f"{stats['best_cutoff']['out_of_scope_caught']:.0%} OOS, "
                     f"loses {stats['best_cutoff']['in_scope_lost']:.0%}",
                     fontsize=9)
        ax.set_xlabel("top-1 retrieval score")
        ax.set_ylabel("questions")
        ax.legend(fontsize=8)

        print(f"\n=== {config} ===")
        print(f"  answerable    mean={stats['in_scope_mean']:.4g}  "
              f"min={stats['in_scope_min']:.4g}")
        print(f"  out of scope  mean={stats['out_of_scope_mean']:.4g}  "
              f"max={stats['out_of_scope_max']:.4g}")
        print(f"  clean gap between the two: {stats['clean_gap']}")
        print(f"  best cutoff {cutoff:.4g} -> catches "
              f"{stats['best_cutoff']['out_of_scope_caught']:.0%} of out-of-scope, "
              f"costs {stats['best_cutoff']['in_scope_lost']:.0%} of answerable")

    fig.suptitle("Top-1 retrieval score: answerable vs out-of-scope questions "
                 "(scales are not comparable between configurations)",
                 fontsize=10)
    fig.tight_layout()
    out_png = ROOT / "reports" / "runs" / f"{args.run}-score-distribution.png"
    fig.savefig(out_png, dpi=140)

    out_json = ROOT / "reports" / "runs" / f"{args.run}-score-separation.json"
    out_json.write_text(json.dumps({"run": args.run, "configs": summary},
                                   indent=2), encoding="utf-8")
    print(f"\n-> {out_png.relative_to(ROOT)}")
    print(f"-> {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
