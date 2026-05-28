"""
Contamination audit: reproducible summary for the repair_clean corpus.

Loads every record from data/indexes/repair_clean/meta.jsonl (the live index),
re-applies should_include_record() with target_benchmark="quixbugs", and saves
a summary that can be committed alongside the paper as evidence of hygiene.

Output (saved to experiments/repair_clean_audit.json):
  total           – records in meta.jsonl
  included        – records that pass should_include_record (quixbugs target)
  excluded        – records that do not pass
  exclusion_reasons – {reason: count}
  quixbugs_overlap  – records whose source_dataset or instance_id matches QuixBugs
  source_breakdown  – {source_dataset: {included, excluded}} counts
  sample_excluded   – first 10 excluded records (id + reason)

Usage:
  python -m src.datasets.audit_corpus \\
      [--meta-path data/indexes/repair_clean/meta.jsonl] \\
      [--out experiments/repair_clean_audit.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.datasets.bugfix_corpus_schema import BugFixRecord, should_include_record

DEFAULT_META = "data/indexes/repair_clean/meta.jsonl"
DEFAULT_OUT = "experiments/repair_clean_audit.json"


def load_meta(path: str) -> list[dict]:
    records: list[dict] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def meta_to_record(raw: dict) -> BugFixRecord:
    """Convert a meta.jsonl entry to a BugFixRecord for filter evaluation."""
    return BugFixRecord(
        id=raw.get("id", ""),
        source_dataset=raw.get("source_dataset", "unknown"),
        source_split=raw.get("source_split", ""),
        language=raw.get("language", "python"),
        task_family=raw.get("task_family", "general_python"),
        repository=raw.get("repository", ""),
        instance_id=raw.get("instance_id", raw.get("id", "")),
        buggy_code=raw.get("buggy_code", "x"),   # non-empty sentinel for validation
        fixed_code=raw.get("fixed_code", raw.get("correct_code", "x")),
        file_path=raw.get("file_path", ""),
        function_name=raw.get("function_name", ""),
        prompt=raw.get("prompt", ""),
        bug_type=raw.get("bug_type", "unknown"),
        failure_signal=raw.get("failure_signal", ""),
        tests=raw.get("tests") or [],
        metadata=raw.get("metadata") or {},
    )


def run_audit(meta_path: str, out_path: str) -> dict:
    if not os.path.exists(meta_path):
        print(f"[ERROR] meta.jsonl not found at {meta_path}")
        sys.exit(1)

    raw_records = load_meta(meta_path)
    total = len(raw_records)
    print(f"Loaded {total} records from {meta_path}")

    included: list[dict] = []
    excluded: list[dict] = []
    exclusion_reasons: Counter = Counter()
    quixbugs_overlap: list[str] = []
    source_breakdown: dict[str, dict] = defaultdict(lambda: {"included": 0, "excluded": 0})

    for raw in raw_records:
        rec = meta_to_record(raw)
        ok, reason = should_include_record(rec, target_benchmark="quixbugs")
        src = rec.source_dataset

        if ok:
            included.append(raw.get("id", "?"))
            source_breakdown[src]["included"] += 1
        else:
            excluded.append({"id": raw.get("id", "?"), "reason": reason})
            exclusion_reasons[reason] += 1
            source_breakdown[src]["excluded"] += 1

        if rec.source_dataset == "quixbugs" or rec.instance_id.startswith("quixbugs_"):
            quixbugs_overlap.append(raw.get("id", "?"))

    summary = {
        "meta_path": meta_path,
        "total": total,
        "included": len(included),
        "excluded": len(excluded),
        "exclusion_rate": len(excluded) / total if total else 0.0,
        "exclusion_reasons": dict(exclusion_reasons.most_common()),
        "quixbugs_overlap_count": len(quixbugs_overlap),
        "quixbugs_overlap_ids": quixbugs_overlap,
        "source_breakdown": dict(source_breakdown),
        "sample_excluded": excluded[:10],
    }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\n=== repair_clean Contamination Audit ===")
    print(f"Total records  : {total}")
    print(f"Included       : {len(included)}")
    print(f"Excluded       : {len(excluded)} ({summary['exclusion_rate']*100:.1f}%)")
    print(f"QuixBugs overlap (excluded by target): {len(quixbugs_overlap)}")
    print(f"\nTop exclusion reasons:")
    for reason, count in exclusion_reasons.most_common(10):
        print(f"  {count:4d}  {reason}")
    print(f"\nSource breakdown:")
    for src, counts in sorted(source_breakdown.items()):
        print(f"  {src:<30} incl={counts['included']:3d}  excl={counts['excluded']:3d}")
    print(f"\nSaved to {out_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Contamination audit for repair_clean corpus")
    parser.add_argument("--meta-path", default=DEFAULT_META)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    run_audit(args.meta_path, args.out)


if __name__ == "__main__":
    main()
