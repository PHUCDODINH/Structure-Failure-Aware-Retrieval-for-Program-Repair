"""
Table 5: Stronger system setting — does the retrieval gain survive inside the
full iterative repair pipeline?

QuixBugs  → rag_candidates=3, rag_max_attempts=1 (3 diverse candidates per attempt)
PyBugHive → rag_max_attempts=2 (iterative repair with failure feedback)

Runs three variants: code_only, raw_text, structured.

Usage:
  # QuixBugs
  python -m src.eval.run_table5 quixbugs \\
      --model gpt-4o --retrieval-profile repair_clean \\
      --limit 40 --prefix quixbugs_gpt4o_table5

  # PyBugHive-black
  python -m src.eval.run_table5 pybughive \\
      --model gpt-4o --dataset-json data/pybughive_black_frozen.json \\
      --retrieval-profile repair_clean \\
      --prefix pybughive_gpt4o_table5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

TABLE5_VARIANTS = ["code_only", "raw_text", "structured"]


def load_frozen_cases(path: str) -> list[dict] | None:
    payload = json.loads(Path(path).read_text())
    if isinstance(payload, dict) and "cases" in payload:
        return [case for case in payload["cases"] if case.get("included", True)]
    return None


def count_passes(results: list[dict]) -> int:
    return sum(1 for r in results if r.get("pass"))


def run_quixbugs(args: argparse.Namespace) -> None:
    from src.eval.evaluate_quixbugs import evaluate_quixbugs

    os.makedirs(args.results_dir, exist_ok=True)
    slug = args.model.replace(".", "").replace("-", "")
    prefix = args.prefix or f"table5_qb_{slug}"

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

    summary: dict = {
        "benchmark": "quixbugs",
        "model": args.model,
        "setting": "stronger (candidates=3)",
        "baseline": {
            "passed": count_passes(baseline_results),
            "total": len(baseline_results),
            "out_file": baseline_path,
        },
        "variants": [],
    }

    for variant in TABLE5_VARIANTS:
        out_path = os.path.join(args.results_dir, f"{prefix}_rag_{variant}.json")
        results = evaluate_quixbugs(
            mode="rag",
            out_file=out_path,
            model=args.model,
            limit=args.limit,
            retrieval_profile=args.retrieval_profile,
            use_failure_signal=True,
            rag_max_attempts=1,
            rag_k=2,
            rag_candidates=3,         # stronger setting
            retrieval_variant=variant,
        )
        passed = count_passes(results)
        summary["variants"].append({
            "variant": variant,
            "passed": passed,
            "total": len(results),
            "pass_rate": passed / len(results) if results else 0.0,
            "delta_vs_baseline": passed - summary["baseline"]["passed"],
            "out_file": out_path,
        })

    _save_and_print(summary, args.results_dir, prefix)


def run_pybughive(args: argparse.Namespace) -> None:
    from src.models.repair_rag import repair_with_rag
    from src.models.repair_baseline import repair_without_rag
    from src.eval.evaluate_pybughive import (
        load_dataset, iter_supported_cases, evaluate_case,
        load_existing_results, save_results, InfrastructureFailure,
    )
    import traceback

    dataset_path = args.dataset_json
    if not dataset_path or not os.path.exists(dataset_path):
        print(f"[ERROR] --dataset-json not found: {dataset_path}")
        sys.exit(1)

    os.makedirs(args.results_dir, exist_ok=True)
    slug = args.model.replace(".", "").replace("-", "")
    prefix = args.prefix or f"table5_pb_{slug}"
    frozen_cases = load_frozen_cases(dataset_path)
    if frozen_cases is None:
        dataset = load_dataset(dataset_path)
        cases = iter_supported_cases(dataset, projects_filter={"black"})
    else:
        cases = frozen_cases
    if args.limit:
        cases = cases[: args.limit]
    repo_cache = Path(args.repo_cache_root)
    workspace = Path(args.workspace_root)
    workspace.mkdir(parents=True, exist_ok=True)

    summary: dict = {
        "benchmark": "pybughive_black",
        "model": args.model,
        "setting": "stronger (max_attempts=2)",
        "variants": [],
    }

    for variant in ["baseline"] + TABLE5_VARIANTS:
        mode = "baseline" if variant == "baseline" else "rag"
        repair_fn = repair_without_rag if mode == "baseline" else repair_with_rag
        out_path = os.path.join(args.results_dir, f"{prefix}_{variant}.json")
        results = load_existing_results(out_path)
        completed = {r["case_id"] for r in results}

        for case in cases:
            case_id = f"{case['repository']}-{case['issue_id']}"
            if case_id in completed:
                continue
            try:
                ok, detail = evaluate_case(
                    case=case,
                    repair_fn=repair_fn,
                    mode=mode,
                    repo_cache_root=repo_cache,
                    workspace_root=workspace,
                    pipenv_bin=args.pipenv_bin,
                    install_timeout=args.install_timeout,
                    test_timeout=args.test_timeout,
                    model=args.model,
                    retrieval_profile=args.retrieval_profile,
                    rag_max_attempts=2,              # stronger setting
                    retrieval_variant=variant if mode == "rag" else "structured",
                )
            except InfrastructureFailure as exc:
                print(f"[ABORT] {exc}")
                break
            except Exception as exc:
                ok, detail = False, f"[ERROR] {exc}\n{traceback.format_exc()}"

            results.append({"case_id": case_id, "pass": ok, "detail": detail,
                            "variant": variant})
            completed.add(case_id)
            save_results(out_path, results)

        passed = count_passes(results)
        summary["variants"].append({
            "variant": variant,
            "passed": passed,
            "total": len(results),
            "pass_rate": passed / len(results) if results else 0.0,
            "out_file": out_path,
        })

    # delta vs baseline
    base_passed = next((v["passed"] for v in summary["variants"] if v["variant"] == "baseline"), 0)
    for v in summary["variants"]:
        v["delta_vs_baseline"] = v["passed"] - base_passed

    _save_and_print(summary, args.results_dir, prefix)


def _save_and_print(summary: dict, results_dir: str, prefix: str) -> None:
    summary_path = os.path.join(results_dir, f"{prefix}_summary.json")
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    bench = summary.get("benchmark", "?")
    setting = summary.get("setting", "")
    print(f"\n=== Table 5: {bench} | {setting} ===")
    base = summary.get("baseline", {})
    if base:
        print(f"  baseline: {base['passed']}/{base['total']}")
    for v in summary.get("variants", []):
        print(f"  {v['variant']:<22} {v['passed']}/{v['total']} "
              f"({v['pass_rate']*100:.1f}%)  delta={v.get('delta_vs_baseline', '?'):+}")
    print(f"Saved to {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Table 5: stronger system setting")
    sub = parser.add_subparsers(dest="benchmark", required=True)

    # -- QuixBugs sub-command --
    qb = sub.add_parser("quixbugs")
    qb.add_argument("--model", required=True)
    qb.add_argument("--retrieval-profile", default="repair_clean")
    qb.add_argument("--limit", type=int, default=40)
    qb.add_argument("--results-dir", default="experiments")
    qb.add_argument("--prefix", default=None)

    # -- PyBugHive sub-command --
    pb = sub.add_parser("pybughive")
    pb.add_argument("--model", required=True)
    pb.add_argument("--dataset-json", required=True,
                    help="Frozen PyBugHive-black cases JSON")
    pb.add_argument("--retrieval-profile", default="repair_clean")
    pb.add_argument("--limit", type=int, default=None)
    pb.add_argument("--results-dir", default="experiments")
    pb.add_argument("--prefix", default=None)
    pb.add_argument("--pipenv-bin", default="pipenv")
    pb.add_argument("--install-timeout", type=int, default=300)
    pb.add_argument("--test-timeout", type=int, default=120)
    pb.add_argument("--repo-cache-root", default="data/external_sources/repo_cache")
    pb.add_argument("--workspace-root", default="temp_pybughive_table5")

    args = parser.parse_args()
    if args.benchmark == "quixbugs":
        run_quixbugs(args)
    else:
        run_pybughive(args)


if __name__ == "__main__":
    main()
