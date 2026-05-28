"""
Table 6: Repeated trials — mean / std / min / max pass rate.

Runs evaluate_quixbugs N times with independent output files and aggregates
variance statistics.  Each trial uses a fresh output path so the resume
mechanism does not suppress re-evaluation.

The primary setting matches Table 2:
  - mode=rag, single attempt, k=2, candidates=1, variant=structured
  - model supplied via --model

Usage:
  python -m src.eval.run_variance_trials \\
      --model gpt-4o \\
      --retrieval-profile repair_clean \\
      --limit 40 \\
      --trials 5 \\
      --variant structured \\
      --results-dir experiments \\
      --prefix quixbugs_gpt4o_variance
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.eval.evaluate_quixbugs import evaluate_quixbugs


def count_passes(results: list[dict]) -> int:
    return sum(1 for r in results if r.get("pass"))


def std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeated trials for variance estimation (Table 6)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--retrieval-profile", default="repair_clean")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--trials", type=int, default=5,
                        help="Number of independent reruns (5 for QuixBugs per plan)")
    parser.add_argument("--variant", default="structured",
                        choices=["structured", "code_only", "raw_text", "raw_text_rerank"])
    parser.add_argument("--mode", default="rag", choices=["rag", "baseline"])
    parser.add_argument("--rag-k", type=int, default=2)
    parser.add_argument("--results-dir", default="experiments")
    parser.add_argument("--prefix", default=None)
    args = parser.parse_args()

    os.makedirs(args.results_dir, exist_ok=True)
    slug = args.model.replace(".", "").replace("-", "")
    prefix = args.prefix or f"variance_{slug}_{args.variant}"

    pass_counts: list[int] = []
    totals: list[int] = []
    trial_files: list[str] = []

    for trial in range(1, args.trials + 1):
        out_path = os.path.join(args.results_dir, f"{prefix}_trial{trial}.json")
        trial_files.append(out_path)
        print(f"\n=== Trial {trial}/{args.trials} ===")

        results = evaluate_quixbugs(
            mode=args.mode,
            out_file=out_path,
            model=args.model,
            limit=args.limit,
            retrieval_profile=args.retrieval_profile if args.mode == "rag" else None,
            use_failure_signal=True,
            rag_max_attempts=1,
            rag_k=args.rag_k,
            rag_candidates=1,
            retrieval_variant=args.variant,
        )
        passed = count_passes(results)
        pass_counts.append(passed)
        totals.append(len(results))
        print(f"Trial {trial}: {passed}/{len(results)}")

    total_problems = totals[0] if totals else 0
    pass_rates = [p / total_problems for p in pass_counts] if total_problems else []
    mean_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0.0
    std_rate = std(pass_rates)
    min_rate = min(pass_rates) if pass_rates else 0.0
    max_rate = max(pass_rates) if pass_rates else 0.0

    summary = {
        "model": args.model,
        "variant": args.variant,
        "mode": args.mode,
        "limit": args.limit,
        "rag_k": args.rag_k,
        "trials": args.trials,
        "total_problems": total_problems,
        "pass_counts": pass_counts,
        "pass_rates": pass_rates,
        "mean_pass_rate": mean_rate,
        "std_pass_rate": std_rate,
        "min_pass_rate": min_rate,
        "max_pass_rate": max_rate,
        "trial_files": trial_files,
    }

    summary_path = os.path.join(args.results_dir, f"{prefix}_variance_summary.json")
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\n=== Variance Summary ({args.trials} trials) ===")
    print(f"Model:    {args.model}  variant={args.variant}")
    print(f"Problems: {total_problems}")
    print(f"Pass counts: {pass_counts}")
    print(f"Mean:  {mean_rate*100:.1f}%  Std: {std_rate*100:.2f}%  "
          f"Min: {min_rate*100:.1f}%  Max: {max_rate*100:.1f}%")
    print(f"Saved to {summary_path}")


if __name__ == "__main__":
    main()
