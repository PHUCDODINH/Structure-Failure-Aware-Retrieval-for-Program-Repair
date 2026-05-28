"""
Freeze a PyBugHive runnable case inclusion list.

Applies iter_supported_cases() to the full PyBugHive dataset, optionally
cross-references against existing result files to mark cases that failed
installation in ALL methods, then writes the frozen list.

Plan inclusion rule:
  - include all manuallyChecked black cases with one non-test Python source
    and valid test steps
  - exclude only cases that fail installation in ALL methods after one clean
    rerun with fixed timeouts
  - if fewer than 15 reproducibly runnable cases remain, treat PyBugHive as
    supporting evidence only (flag is written to the output)

Output: data/pybughive_black_frozen.json
  {
    "meta": { "total_candidates": ..., "included_count": ..., "supporting_only": ... },
    "cases": [
      { "case_id": ..., "repository": ..., "issue_id": ..., "file_path": ...,
        "install_ok": true/false/null, "included": true/false,
        "exclusion_reason": null / "install_failed_all_methods" }
    ]
  }

Usage:
  python -m src.eval.freeze_pybughive_list \\
      --dataset-json path/to/pybughive.json \\
      --result-files experiments/pybughive_baseline_*.json \\
                     experiments/pybughive_rag_*.json \\
      [--out data/pybughive_black_frozen.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.eval.evaluate_pybughive import iter_supported_cases, load_dataset

SUPPORTING_ONLY_THRESHOLD = 15
DEFAULT_OUT = "data/pybughive_black_frozen.json"


def load_install_failures(result_files: list[str]) -> set[str]:
    """
    Returns the set of case_ids that have 'detail' containing '[INSTALL FAILED]'
    in at least one result file.  Cases that fail install in ALL provided result
    files are considered installation-failures.
    """
    failures_by_case: dict[str, int] = {}
    files_with_case: dict[str, int] = {}

    for path in result_files:
        if not os.path.exists(path):
            continue
        try:
            results = json.loads(Path(path).read_text())
        except Exception:
            continue
        for row in results:
            cid = row.get("case_id", "")
            if not cid:
                continue
            files_with_case[cid] = files_with_case.get(cid, 0) + 1
            if "[INSTALL FAILED]" in (row.get("detail") or ""):
                failures_by_case[cid] = failures_by_case.get(cid, 0) + 1

    # A case fails in ALL methods if failure count == files_containing_it
    return {
        cid for cid, fail_count in failures_by_case.items()
        if fail_count >= files_with_case.get(cid, 1)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze PyBugHive inclusion list")
    parser.add_argument("--dataset-json", required=True,
                        help="Full PyBugHive dataset JSON")
    parser.add_argument("--result-files", nargs="*", default=[],
                        help="Existing result JSONs to detect install failures (supports globs)")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--project",
        default=None,
        help="Single repository/project to freeze. Kept for backwards compatibility.",
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=None,
        help="One or more repositories/projects to freeze into the same list.",
    )
    args = parser.parse_args()

    # Expand globs
    result_files: list[str] = []
    for pattern in args.result_files:
        expanded = glob.glob(pattern)
        result_files.extend(expanded if expanded else [pattern])

    projects = args.projects or [args.project or "black"]
    dataset = load_dataset(args.dataset_json)
    candidates = iter_supported_cases(dataset, projects_filter=set(projects))
    project_label = ",".join(projects)
    print(f"Candidate {project_label} cases (manuallyChecked, single-file, valid test steps): {len(candidates)}")

    install_failures = load_install_failures(result_files)
    print(f"Cases failing install in all tested methods: {len(install_failures)}")

    frozen: list[dict] = []
    for case in candidates:
        cid = f"{case['repository']}-{case['issue_id']}"
        install_failed_all = cid in install_failures
        included = not install_failed_all
        frozen.append({
            "case_id": cid,
            "username": case["username"],
            "repository": case["repository"],
            "issue_id": case["issue_id"],
            "title": case["title"],
            "file_path": case["file_path"],
            "buggy_commit": case["buggy_commit"],
            "fixed_commit": case["fixed_commit"],
            "test_steps": case["test_steps"],
            "install_steps": case["install_steps"],
            "buggy_code": "",
            "fixed_code": "",
            "failure_signal": "",
            "install_ok": (False if install_failed_all else None),
            "included": included,
            "exclusion_reason": "install_failed_all_methods" if install_failed_all else None,
        })

    included_cases = [f for f in frozen if f["included"]]
    supporting_only = len(included_cases) < SUPPORTING_ONLY_THRESHOLD

    output = {
        "meta": {
            "total_candidates": len(candidates),
            "project": projects[0] if len(projects) == 1 else None,
            "projects": projects,
            "included_count": len(included_cases),
            "excluded_count": len(frozen) - len(included_cases),
            "supporting_only": supporting_only,
            "supporting_only_reason": (
                f"Fewer than {SUPPORTING_ONLY_THRESHOLD} reproducibly runnable cases"
                if supporting_only else None
            ),
        },
        "cases": frozen,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(output, fh, indent=2)

    print(f"\n=== PyBugHive Frozen List ({project_label}) ===")
    print(f"Total candidates : {len(candidates)}")
    print(f"Included         : {len(included_cases)}")
    print(f"Excluded         : {len(frozen) - len(included_cases)}")
    if supporting_only:
        print(f"WARNING: Only {len(included_cases)} runnable cases — treat as supporting evidence only.")
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
