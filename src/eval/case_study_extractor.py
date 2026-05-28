"""
Case-study package (requirement G).

Reads existing trace directories and finds four categories of cases:
  win_structured_qb  – QuixBugs: structured passes, code_only/raw_text fails
  win_structured_pb  – PyBugHive-black: structured passes, baseline fails
  loss_structured    – structured fails even though another variant passes
  tie_interesting    – structured retrieves visibly different examples (even if outcome ties)

For each selected case the script writes a human-readable Markdown case study
showing:
  - buggy code
  - raw failure signal
  - structured failure state
  - top-2 retrieval BEFORE structured reranking (i.e., code_only top-2)
  - top-2 retrieval AFTER structured reranking
  - generated patch
  - final outcome

Usage:
  python -m src.eval.case_study_extractor \\
      --trace-dirs traces/quixbugs_structured traces/quixbugs_code_only \\
      --out-dir experiments/case_studies \\
      [--max-wins 2 --max-losses 1]

The script can also be pointed at a single trace directory that contains
traces for multiple variants (named <variant>__<problem>__attempt<n>.json).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.retrieval.repair_metadata import infer_repair_metadata, metadata_overlap


# ---------------------------------------------------------------------------
# Trace loading
# ---------------------------------------------------------------------------

def load_traces_from_dirs(trace_dirs: list[str]) -> dict[str, dict[str, dict]]:
    """
    Returns {problem: {variant: trace_dict}}.
    Trace filenames: <variant>__<problem>__attempt<n>.json
    Only the highest-attempt trace per (problem, variant) is kept.
    """
    traces: dict[str, dict[str, dict]] = {}
    for d in trace_dirs:
        if not os.path.isdir(d):
            continue
        dir_variant = _infer_variant_from_dir(d)
        for fname in sorted(os.listdir(d)):
            if not fname.endswith(".json"):
                continue
            parts = fname[:-5].split("__")
            if len(parts) < 3:
                continue
            variant, problem = parts[0], parts[1]
            if variant == "rag" and dir_variant:
                variant = dir_variant
            trace_path = os.path.join(d, fname)
            try:
                trace = json.loads(Path(trace_path).read_text())
            except Exception:
                continue
            traces.setdefault(problem, {})[variant] = trace
    return traces


def _infer_variant_from_dir(path: str) -> str | None:
    name = Path(path).name.lower()
    for variant in ("raw_text_rerank", "code_only", "raw_text", "structured", "baseline"):
        if variant in name:
            return variant
    return None


# ---------------------------------------------------------------------------
# Candidate comparison helpers
# ---------------------------------------------------------------------------

def _top_k_ids(trace: dict, k: int = 2) -> list[str]:
    """Return the IDs of the top-k retrieved examples from a trace."""
    examples = trace.get("retrieved_examples") or []
    return [ex.get("id", "") for ex in examples[:k]]


def _retrieval_debug(trace: dict) -> dict:
    cand = trace.get("candidate_results") or []
    if cand:
        best = max(cand, key=lambda c: (c.get("pass", False), c.get("passed_tests", 0)))
        return best.get("retrieval_debug") or {}
    return {}


def candidates_differ(trace_a: dict, trace_b: dict, k: int = 2) -> bool:
    return set(_top_k_ids(trace_a, k)) != set(_top_k_ids(trace_b, k))


# ---------------------------------------------------------------------------
# Case selection logic
# ---------------------------------------------------------------------------

def select_cases(
    traces: dict[str, dict[str, dict]],
    max_wins: int = 2,
    max_losses: int = 1,
) -> dict[str, list[str]]:
    """Return {category: [problem, ...]}."""
    wins: list[str] = []
    losses: list[str] = []
    interesting_ties: list[str] = []

    for problem, variants in traces.items():
        struct = variants.get("structured") or variants.get("rag")
        code_only = variants.get("code_only")
        raw_text = variants.get("raw_text")
        baseline = variants.get("baseline")

        struct_pass = (struct or {}).get("pass", False)
        code_pass = (code_only or {}).get("pass", False)
        raw_pass = (raw_text or {}).get("pass", False)
        base_pass = (baseline or {}).get("pass", False)

        weak_pass = code_pass or raw_pass or base_pass

        if struct_pass and not weak_pass and len(wins) < max_wins:
            wins.append(problem)
        elif not struct_pass and weak_pass and len(losses) < max_losses:
            losses.append(problem)
        elif struct and code_only and candidates_differ(struct, code_only):
            interesting_ties.append(problem)

    return {
        "win_structured": wins,
        "loss_structured": losses,
        "interesting_tie": interesting_ties[:1],
    }


# ---------------------------------------------------------------------------
# Case study formatter
# ---------------------------------------------------------------------------

def _fmt_failure_state(fs: dict | None) -> str:
    if not fs:
        return "_No structured failure state recorded._\n"
    lines = [
        f"- **failure_mode**: `{fs.get('failure_mode', '')}`",
        f"- **exception_type**: `{fs.get('exception_type', '')}`",
        f"- **test_name**: `{fs.get('test_name', '')}`",
        f"- **contract_tags**: `{fs.get('contract_tags', [])}`",
        f"- **suspicious_symbols** (top-5): `{(fs.get('suspicious_symbols') or [])[:5]}`",
        f"- **assertion_summary**: {fs.get('assertion_summary', '')[:120]}",
    ]
    return "\n".join(lines) + "\n"


def _fmt_examples(examples: list[dict] | None, label: str) -> str:
    if not examples:
        return f"_No {label} examples recorded._\n"
    parts = [f"**{label}**\n"]
    for i, ex in enumerate(examples[:2], 1):
        bid = ex.get("id", "?")
        lesson = ex.get("repair_lesson", "")
        buggy = ex.get("buggy_snippet", "")[:300]
        fixed = ex.get("fixed_snippet", "")[:300]
        parts.append(f"Example {i} (id={bid})")
        if lesson:
            parts.append(f"Lesson: {lesson}")
        parts.append(f"```python\n# buggy\n{buggy}\n# fixed\n{fixed}\n```\n")
    return "\n".join(parts)


def format_case_study(problem: str, traces: dict[str, dict], category: str) -> str:
    struct = traces.get("structured") or traces.get("rag") or {}
    code_only = traces.get("code_only") or {}

    buggy_code = struct.get("input_buggy_code", "")
    raw_signal = struct.get("failure_signal", "")
    failure_state = struct.get("failure_state")
    generated_code = struct.get("generated_code", "")
    outcome = "PASS" if struct.get("pass") else "FAIL"

    struct_examples = struct.get("retrieved_examples") or []
    code_only_examples = code_only.get("retrieved_examples") or []

    md = [
        f"# Case Study: `{problem}`",
        f"**Category**: {category}  |  **Outcome (structured)**: {outcome}\n",
        "## Buggy Code",
        f"```python\n{buggy_code[:800]}\n```\n",
        "## Raw Failure Signal",
        f"```\n{raw_signal[:600]}\n```\n",
        "## Structured Failure State",
        _fmt_failure_state(failure_state),
        "## Retrieval Comparison",
        _fmt_examples(code_only_examples, "code_only top-2 (before structured reranking)"),
        _fmt_examples(struct_examples, "structured top-2 (after reranking)"),
        "## Generated Patch (structured)",
        f"```python\n{generated_code[:800]}\n```\n",
        f"## Final Outcome: **{outcome}**\n",
    ]
    return "\n".join(md)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Case study extractor (requirement G)")
    parser.add_argument("--trace-dirs", nargs="+", required=True,
                        help="One or more trace directories")
    parser.add_argument("--out-dir", default="experiments/case_studies")
    parser.add_argument("--max-wins", type=int, default=2)
    parser.add_argument("--max-losses", type=int, default=1)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    traces = load_traces_from_dirs(args.trace_dirs)
    print(f"Loaded traces for {len(traces)} problems across variants: "
          f"{sorted({v for vd in traces.values() for v in vd})}")

    selected = select_cases(traces, max_wins=args.max_wins, max_losses=args.max_losses)
    total = sum(len(v) for v in selected.values())
    if total == 0:
        print("No suitable cases found. Run the full variant comparison first so that "
              "traces for 'structured' and 'code_only' exist in the same directory.")
        sys.exit(0)

    index: list[dict] = []
    for category, problems in selected.items():
        for problem in problems:
            md = format_case_study(problem, traces.get(problem, {}), category)
            out_path = os.path.join(args.out_dir, f"{category}__{problem}.md")
            Path(out_path).write_text(md)
            print(f"Wrote {out_path}")
            index.append({"problem": problem, "category": category, "file": out_path})

    index_path = os.path.join(args.out_dir, "index.json")
    with open(index_path, "w") as fh:
        json.dump(index, fh, indent=2)
    print(f"\nIndex saved to {index_path}")
    print(f"Total case studies: {len(index)}")


if __name__ == "__main__":
    main()
