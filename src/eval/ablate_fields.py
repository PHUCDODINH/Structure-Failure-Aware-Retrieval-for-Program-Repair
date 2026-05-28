"""
Table 3: Per-field ablation — downstream pass-rate drop.

Starts from the full structured reranker and disables one score component at
a time.  Runs evaluate_quixbugs (and optionally evaluate_pybughive) for each
ablation condition and reports the pass-rate drop vs. the intact method.

Ablation conditions
-------------------
full              – all components active  (reference)
no_contract_tags  – zero contract_tag_overlap
no_suspicious_symbols – zero symbol_overlap
no_failure_mode   – zero failure_mode_compat
no_exception_type – zero exception_compat

Usage:
  python -m src.eval.ablate_fields \\
      --model gpt-4o \\
      --retrieval-profile repair_clean \\
      --limit 40 \\
      --results-dir experiments \\
      --prefix quixbugs_gpt4o_fieldablation
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.eval.evaluate_quixbugs import evaluate_quixbugs


# Maps condition name -> frozenset of active score components to disable.
# test_name and assertion_summary are logged in the failure state, but are not
# score components yet; keeping them out avoids misleading ablation rows.
ABLATION_CONDITIONS: list[tuple[str, frozenset[str]]] = [
    ("full",                   frozenset()),
    ("no_contract_tags",       frozenset({"contract_tags"})),
    ("no_suspicious_symbols",  frozenset({"suspicious_symbols"})),
    ("no_failure_mode",        frozenset({"failure_mode"})),
    ("no_exception_type",      frozenset({"exception_type"})),
]


def count_passes(results: list[dict]) -> int:
    return sum(1 for r in results if r.get("pass"))


def load_frozen_pybughive_cases(path: str) -> list[dict]:
    payload = json.loads(Path(path).read_text())
    if isinstance(payload, dict) and "cases" in payload:
        return [case for case in payload["cases"] if case.get("included", True)]
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported PyBugHive cases file shape: {path}")


def run_pybughive_condition(args: argparse.Namespace, condition: str, disabled: frozenset[str]) -> dict:
    from src.models.repair_rag import repair_with_rag
    from src.eval.evaluate_pybughive import (
        InfrastructureFailure,
        evaluate_case,
        load_existing_results,
        save_results,
    )
    import traceback

    cases = load_frozen_pybughive_cases(args.pybughive_path)
    if args.limit:
        cases = cases[: args.limit]

    out_path = os.path.join(args.results_dir, f"{args.prefix or 'fieldablation'}_pybughive_{condition}.json")
    results = load_existing_results(out_path)
    completed = {row["case_id"] for row in results}
    for case in cases:
        case_id = f"{case['repository']}-{case['issue_id']}"
        if case_id in completed:
            continue
        try:
            ok, detail = evaluate_case(
                case=case,
                repair_fn=repair_with_rag,
                mode="rag",
                repo_cache_root=Path(args.repo_cache_root),
                workspace_root=Path(args.workspace_root),
                pipenv_bin=args.pipenv_bin,
                install_timeout=args.install_timeout,
                test_timeout=args.test_timeout,
                model=args.model,
                retrieval_profile=args.retrieval_profile,
                rag_max_attempts=1,
                retrieval_variant="structured",
                include_case_metadata=False,
                disabled_components=disabled if disabled else None,
            )
        except InfrastructureFailure as exc:
            print(f"[ABORT] {exc}")
            break
        except Exception as exc:
            ok, detail = False, f"[ERROR] {exc}\n{traceback.format_exc()}"
        results.append({"case_id": case_id, "pass": ok, "detail": detail, "condition": condition})
        completed.add(case_id)
        save_results(out_path, results)

    passed = count_passes(results)
    return {
        "condition": condition,
        "disabled_components": sorted(disabled),
        "benchmark": "pybughive_black",
        "passed": passed,
        "total": len(results),
        "pass_rate": passed / len(results) if results else 0.0,
        "out_file": out_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Per-field ablation (Table 3)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--retrieval-profile", default="repair_clean")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--rag-k", type=int, default=2)
    parser.add_argument("--results-dir", default="experiments")
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--pybughive-path", default=None,
                        help="Frozen PyBugHive-black cases JSON (optional)")
    parser.add_argument("--repo-cache-root", default="data/external_sources/repo_cache")
    parser.add_argument("--workspace-root", default="temp_pybughive_fieldablation")
    parser.add_argument("--pipenv-bin", default="pipenv")
    parser.add_argument("--install-timeout", type=int, default=300)
    parser.add_argument("--test-timeout", type=int, default=120)
    args = parser.parse_args()

    os.makedirs(args.results_dir, exist_ok=True)
    slug = args.model.replace(".", "").replace("-", "")
    prefix = args.prefix or f"fieldablation_{slug}"

    rows: list[dict] = []

    for condition, disabled in ABLATION_CONDITIONS:
        out_path = os.path.join(args.results_dir, f"{prefix}_{condition}.json")
        print(f"\n=== Condition: {condition} (disabled={sorted(disabled) or 'none'}) ===")

        results = evaluate_quixbugs(
            mode="rag",
            out_file=out_path,
            model=args.model,
            limit=args.limit,
            retrieval_profile=args.retrieval_profile,
            use_failure_signal=True,
            rag_max_attempts=1,
            rag_k=args.rag_k,
            rag_candidates=1,
            retrieval_variant="structured",
            disabled_components=disabled if disabled else None,
        )
        passed = count_passes(results)
        rows.append({
            "condition": condition,
            "disabled_components": sorted(disabled),
            "benchmark": "quixbugs",
            "passed": passed,
            "total": len(results),
            "pass_rate": passed / len(results) if results else 0.0,
            "out_file": out_path,
        })

        if args.pybughive_path:
            print(f"\n=== PyBugHive condition: {condition} ===")
            rows.append(run_pybughive_condition(args, condition, disabled))

    # Compute delta vs full (first row)
    full_by_benchmark = {
        row["benchmark"]: row["passed"]
        for row in rows
        if row["condition"] == "full"
    }
    for row in rows:
        row["delta_vs_full"] = row["passed"] - full_by_benchmark.get(row["benchmark"], 0)

    summary_path = os.path.join(args.results_dir, f"{prefix}_summary.json")
    with open(summary_path, "w") as fh:
        json.dump({"model": args.model, "limit": args.limit, "rag_k": args.rag_k,
                   "conditions": rows}, fh, indent=2)

    _print_table(rows)
    print(f"\nSaved summary to {summary_path}")


def _print_table(rows: list[dict]) -> None:
    print(f"\n{'Condition':<26} {'passed':>7} {'total':>6} {'pass%':>7} {'delta':>7}")
    print("-" * 58)
    for row in rows:
        print(
            f"{row['condition']:<26}"
            f" {row['passed']:>7}"
            f" {row['total']:>6}"
            f" {row['pass_rate']*100:>6.1f}%"
            f" {row['delta_vs_full']:>+7}"
        )


if __name__ == "__main__":
    main()
