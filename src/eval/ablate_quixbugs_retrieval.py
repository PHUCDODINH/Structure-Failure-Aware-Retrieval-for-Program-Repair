import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.eval.evaluate_quixbugs import evaluate_quixbugs


def parse_ks(raw: str) -> list[int]:
    values: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        value = int(piece)
        if value < 1:
            raise ValueError("All k values must be >= 1")
        values.append(value)
    if not values:
        raise ValueError("At least one k value is required")
    return values


def parse_variants(raw: str) -> list[str]:
    allowed = {"structured", "code_only", "raw_text", "raw_text_rerank"}
    variants = [piece.strip() for piece in raw.split(",") if piece.strip()]
    unknown = [variant for variant in variants if variant not in allowed]
    if unknown:
        raise ValueError(f"Unknown retrieval variants: {unknown}")
    if not variants:
        raise ValueError("At least one retrieval variant is required")
    return variants


def count_passes(results: list[dict]) -> int:
    return sum(1 for row in results if row.get("pass"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Table 2 (primary): use defaults --ks 2 --rag-candidates 1 --rag-max-attempts 1\n"
            "Table 5 (stronger): use --ks 2 --rag-candidates 3 --rag-max-attempts 1\n"
        )
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--ks", default="2",
                        help="Comma-separated k values (use '2' for primary/Table-2 setting)")
    parser.add_argument("--variants", default="code_only,raw_text,raw_text_rerank,structured")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--retrieval-profile", default="repair_clean")
    parser.add_argument("--rag-candidates", type=int, default=1,
                        help="Candidates per attempt (1=primary/Table-2, 3=stronger/Table-5)")
    parser.add_argument("--rag-max-attempts", type=int, default=1,
                        help="Max repair attempts (1=primary, higher=iterative)")
    parser.add_argument("--results-dir", default="experiments")
    parser.add_argument("--prefix", default=None)
    args = parser.parse_args()

    ks = parse_ks(args.ks)
    variants = parse_variants(args.variants)
    os.makedirs(args.results_dir, exist_ok=True)

    prefix = args.prefix or f"quixbugs_{args.model.replace('.', '').replace('-', '')}_ablation"
    baseline_path = os.path.join(args.results_dir, f"{prefix}_baseline.json")
    baseline_results = evaluate_quixbugs(
        mode="baseline",
        out_file=baseline_path,
        model=args.model,
        limit=args.limit,
        use_failure_signal=True,
        rag_max_attempts=1,
        rag_k=1,
        rag_candidates=1,
    )

    summary = {
        "model": args.model,
        "limit": args.limit,
        "retrieval_profile": args.retrieval_profile,
        "rag_candidates": args.rag_candidates,
        "rag_max_attempts": args.rag_max_attempts,
        "baseline": {
            "out_file": baseline_path,
            "passed": count_passes(baseline_results),
            "total": len(baseline_results),
        },
        "rag": [],
    }

    for variant in variants:
        for k in ks:
            out_path = os.path.join(args.results_dir, f"{prefix}_rag_{variant}_k{k}.json")
            rag_results = evaluate_quixbugs(
                mode="rag",
                out_file=out_path,
                model=args.model,
                limit=args.limit,
                retrieval_profile=args.retrieval_profile,
                use_failure_signal=True,
                rag_max_attempts=args.rag_max_attempts,
                rag_k=k,
                rag_candidates=args.rag_candidates,
                retrieval_variant=variant,
            )
            passed = count_passes(rag_results)
            summary["rag"].append(
                {
                    "variant": variant,
                    "k": k,
                    "out_file": out_path,
                    "passed": passed,
                    "total": len(rag_results),
                    "delta_vs_baseline": passed - summary["baseline"]["passed"],
                }
            )

    summary_path = os.path.join(args.results_dir, f"{prefix}_summary.json")
    with open(summary_path, "w") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
