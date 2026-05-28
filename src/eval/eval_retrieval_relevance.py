"""
Tables 1 & 4: Retrieval relevance evaluation (no LLM calls).

For each QuixBugs problem (and optionally PyBugHive-black cases supplied via
--pybughive-path), retrieves candidates under every retrieval variant and
measures how well the top-k candidates match the ground-truth fix.

Table 1 metrics (per variant):
  top1/top2/top5_tag_compat   – mean Jaccard of retrieved repair_pattern_tags
                                 vs ground-truth repair_pattern_tags
  top1_edit_scope_match       – fraction where top-1 edit_scope equals GT

Table 4 metrics (per query, aggregated):
  gt_tag_overlap              – Jaccard(GT.repair_pattern_tags, candidate)
  gt_symbol_overlap           – Jaccard(GT.suspicious_symbols, candidate)
  edit_scope_match            – 1 if edit_scope matches GT, else 0
  (reported per variant so reader can see structured > code_only > raw_text)

Usage:
  python -m src.eval.eval_retrieval_relevance \\
      --model gpt-4o --retrieval-profile repair_clean \\
      [--pybughive-path data/pybughive_black_cases.json] \\
      --out experiments/retrieval_relevance.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.eval.evaluate_quixbugs import (
    BUGGY_DIR,
    ALT_BUGGY_DIR,
    autodetect_problems,
    find_test_file,
    select_buggy_source,
)
from src.models.repair_rag import retrieve_examples, SEARCH_POOL_SIZE
from src.retrieval.repair_metadata import infer_repair_metadata, metadata_overlap

VARIANTS = ["code_only", "raw_text", "raw_text_rerank", "structured"]
TOP_KS = [1, 2, 5]


# ---------------------------------------------------------------------------
# Ground-truth repair metadata helpers
# ---------------------------------------------------------------------------

def load_counterpart_code(problem: str, source_label: str) -> str | None:
    counterpart_dir = ALT_BUGGY_DIR if source_label == "buggy" else BUGGY_DIR
    path = os.path.join(counterpart_dir, f"{problem}.py")
    if os.path.exists(path):
        return Path(path).read_text()
    return None


def ground_truth_metadata(buggy_code: str, correct_code: str) -> dict:
    return infer_repair_metadata({"buggy_code": buggy_code, "fixed_code": correct_code})


# ---------------------------------------------------------------------------
# Per-candidate compatibility scores vs. ground truth
# ---------------------------------------------------------------------------

def candidate_compat(candidate: dict, gt_meta: dict) -> dict:
    c_meta = candidate.get("repair_metadata") or infer_repair_metadata(candidate)
    tag_compat = metadata_overlap(
        gt_meta.get("repair_pattern_tags") or [],
        c_meta.get("repair_pattern_tags") or [],
    )
    symbol_compat = metadata_overlap(
        gt_meta.get("suspicious_symbols") or [],
        c_meta.get("suspicious_symbols") or [],
    )
    scope_match = int(
        bool(gt_meta.get("edit_scope"))
        and gt_meta.get("edit_scope") == c_meta.get("edit_scope")
    )
    return {
        "tag_compat": tag_compat,
        "symbol_compat": symbol_compat,
        "scope_match": scope_match,
        "candidate_repair_metadata": c_meta,
    }


# ---------------------------------------------------------------------------
# Evaluate one problem across all variants
# ---------------------------------------------------------------------------

def eval_one_problem(
    problem: str,
    buggy_code: str,
    failure_signal: str,
    gt_meta: dict,
    retrieval_profile: str | None,
) -> dict:
    result: dict = {"problem": problem, "gt_meta": gt_meta, "variants": {}}

    for variant in VARIANTS:
        examples, debug = retrieve_examples(
            buggy_code,
            failure_signal=failure_signal,
            k=max(TOP_KS),
            retrieval_profile=retrieval_profile,
            retrieval_variant=variant,
            return_debug=True,
        )
        # examples is already in post-rerank order (top-k); candidate_pool
        # entries only carry scoring metadata, not full corpus records.
        ranked_compat: list[dict] = []
        for idx, ex in enumerate(examples):
            compat = candidate_compat(ex, gt_meta)
            compat["rank"] = idx + 1
            compat["candidate_id"] = ex.get("id", "")
            ranked_compat.append(compat)

        # Top-k tag compatibility scores
        topk_scores: dict[int, float] = {}
        for k in TOP_KS:
            slice_ = ranked_compat[:k]
            if slice_:
                topk_scores[k] = mean(c["tag_compat"] for c in slice_)
            else:
                topk_scores[k] = 0.0

        top1_scope_match = ranked_compat[0]["scope_match"] if ranked_compat else 0

        result["variants"][variant] = {
            "topk_tag_compat": topk_scores,
            "top1_scope_match": top1_scope_match,
            "top1_symbol_compat": ranked_compat[0]["symbol_compat"] if ranked_compat else 0.0,
            "ranked_compat": ranked_compat,
        }

    return result


# ---------------------------------------------------------------------------
# QuixBugs evaluation
# ---------------------------------------------------------------------------

def run_quixbugs(
    retrieval_profile: str | None,
    limit: int | None,
) -> list[dict]:
    problems = autodetect_problems()
    if limit:
        problems = problems[:limit]

    rows: list[dict] = []
    for problem in problems:
        testfile = find_test_file(problem)
        if testfile is None:
            print(f"[SKIP] {problem}: no test file")
            continue

        try:
            source = select_buggy_source(problem, testfile)
        except Exception as exc:
            print(f"[SKIP] {problem}: {exc}")
            continue

        correct_code = load_counterpart_code(problem, source["label"])
        if correct_code is None:
            print(f"[SKIP] {problem}: no counterpart code")
            continue

        buggy_code = source["code"]
        failure_signal = source["failure_signal"]
        gt_meta = ground_truth_metadata(buggy_code, correct_code)

        print(f"  {problem}: gt_tags={gt_meta['repair_pattern_tags']} scope={gt_meta['edit_scope']}")
        row = eval_one_problem(problem, buggy_code, failure_signal, gt_meta, retrieval_profile)
        row["benchmark"] = "quixbugs"
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# PyBugHive-black evaluation (optional)
# ---------------------------------------------------------------------------

def run_pybughive(
    cases_path: str,
    retrieval_profile: str | None,
    limit: int | None,
) -> list[dict]:
    payload = json.loads(Path(cases_path).read_text())
    cases = payload.get("cases", []) if isinstance(payload, dict) else payload
    cases = [case for case in cases if case.get("included", True)]
    if limit:
        cases = cases[:limit]

    rows: list[dict] = []
    for case in cases:
        buggy_code = case.get("buggy_code", "")
        fixed_code = case.get("fixed_code", "")
        failure_signal = case.get("failure_signal", "")
        if not buggy_code or not fixed_code:
            continue

        gt_meta = ground_truth_metadata(buggy_code, fixed_code)
        case_id = f"{case.get('repository', 'unk')}-{case.get('issue_id', 'unk')}"
        print(f"  {case_id}: gt_tags={gt_meta['repair_pattern_tags']}")
        row = eval_one_problem(case_id, buggy_code, failure_signal, gt_meta, retrieval_profile)
        row["benchmark"] = "pybughive_black"
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def aggregate(rows: list[dict], benchmark: str) -> dict:
    filtered = [r for r in rows if r.get("benchmark") == benchmark]
    if not filtered:
        return {}

    summary: dict = {"benchmark": benchmark, "n": len(filtered), "variants": {}}
    for variant in VARIANTS:
        tag_scores: dict[int, list[float]] = {k: [] for k in TOP_KS}
        scope_matches: list[int] = []
        symbol_scores: list[float] = []

        for row in filtered:
            v = row["variants"].get(variant, {})
            for k in TOP_KS:
                tag_scores[k].append(v.get("topk_tag_compat", {}).get(k, 0.0))
            scope_matches.append(v.get("top1_scope_match", 0))
            symbol_scores.append(v.get("top1_symbol_compat", 0.0))

        summary["variants"][variant] = {
            "top1_tag_compat": mean(tag_scores[1]) if tag_scores[1] else 0.0,
            "top2_tag_compat": mean(tag_scores[2]) if tag_scores[2] else 0.0,
            "top5_tag_compat": mean(tag_scores[5]) if tag_scores[5] else 0.0,
            "top1_edit_scope_match_rate": mean(scope_matches) if scope_matches else 0.0,
            "top1_symbol_compat": mean(symbol_scores) if symbol_scores else 0.0,
        }

    return summary


def print_table(summary: dict) -> None:
    benchmark = summary.get("benchmark", "?")
    n = summary.get("n", 0)
    print(f"\n=== {benchmark.upper()} (n={n}) ===")
    header = f"{'Variant':<22} {'top1_tag':>9} {'top2_tag':>9} {'top5_tag':>9} {'scope_match':>12} {'symbol':>8}"
    print(header)
    print("-" * len(header))
    for variant in VARIANTS:
        v = summary.get("variants", {}).get(variant, {})
        print(
            f"{variant:<22}"
            f" {v.get('top1_tag_compat', 0):>9.3f}"
            f" {v.get('top2_tag_compat', 0):>9.3f}"
            f" {v.get('top5_tag_compat', 0):>9.3f}"
            f" {v.get('top1_edit_scope_match_rate', 0):>12.3f}"
            f" {v.get('top1_symbol_compat', 0):>8.3f}"
        )


# ---------------------------------------------------------------------------
# Manual audit template export (Table 1 requirement)
# ---------------------------------------------------------------------------

def export_manual_audit_template(
    rows: list[dict],
    out_path: str,
    n_quixbugs: int = 10,
    n_pybughive: int = 10,
) -> None:
    """
    Write a JSON template for the 20-case manual relevance audit.
    Each entry contains top-1 retrieved candidate per variant so an annotator
    can mark 'relevant' (1) or 'not relevant' (0) for each.
    """
    qb = [r for r in rows if r.get("benchmark") == "quixbugs"][:n_quixbugs]
    pb = [r for r in rows if r.get("benchmark") == "pybughive_black"][:n_pybughive]
    selected = qb + pb

    template: list[dict] = []
    for row in selected:
        entry: dict = {
            "problem": row["problem"],
            "benchmark": row.get("benchmark", ""),
            "gt_edit_scope": row.get("gt_meta", {}).get("edit_scope", ""),
            "gt_repair_pattern_tags": row.get("gt_meta", {}).get("repair_pattern_tags", []),
            "variants": {},
        }
        for variant in VARIANTS:
            v_data = row.get("variants", {}).get(variant, {})
            ranked = v_data.get("ranked_compat", [])
            top1 = ranked[0] if ranked else {}
            entry["variants"][variant] = {
                "top1_candidate_id": top1.get("candidate_id", ""),
                "top1_tag_compat_auto": round(top1.get("tag_compat", 0.0), 3),
                "top1_edit_scope": top1.get("candidate_repair_metadata", {}).get("edit_scope", ""),
                "top1_repair_pattern_tags": top1.get(
                    "candidate_repair_metadata", {}
                ).get("repair_pattern_tags", []),
                "manually_relevant": None,  # annotator fills this: 1 or 0
            }
        template.append(entry)

    with open(out_path, "w") as fh:
        json.dump(template, fh, indent=2)
    print(f"Manual audit template ({len(template)} tasks) saved to {out_path}")
    print("Fill in 'manually_relevant': 1 (fix-relevant) or 0 (not relevant) for each variant entry.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval relevance evaluation (Tables 1 & 4)")
    parser.add_argument("--retrieval-profile", default="repair_clean")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of problems per benchmark")
    parser.add_argument("--pybughive-path", default=None, help="Path to frozen PyBugHive-black cases JSON")
    parser.add_argument("--out", default="experiments/retrieval_relevance.json")
    parser.add_argument("--export-manual-audit", default=None,
                        metavar="PATH",
                        help="Export a 20-task manual annotation template to this JSON path")
    args = parser.parse_args()

    os.makedirs("experiments", exist_ok=True)
    all_rows: list[dict] = []

    print("--- QuixBugs ---")
    qb_rows = run_quixbugs(args.retrieval_profile, args.limit)
    all_rows.extend(qb_rows)

    if args.pybughive_path and os.path.exists(args.pybughive_path):
        print("--- PyBugHive-black ---")
        pb_rows = run_pybughive(args.pybughive_path, args.retrieval_profile, args.limit)
        all_rows.extend(pb_rows)

    qb_summary = aggregate(all_rows, "quixbugs")
    pb_summary = aggregate(all_rows, "pybughive_black")

    output = {
        "summaries": [s for s in [qb_summary, pb_summary] if s],
        "per_problem": all_rows,
    }

    with open(args.out, "w") as fh:
        json.dump(output, fh, indent=2)
    print(f"\nSaved to {args.out}")

    for summary in output["summaries"]:
        print_table(summary)

    if args.export_manual_audit:
        export_manual_audit_template(all_rows, args.export_manual_audit)


if __name__ == "__main__":
    main()
