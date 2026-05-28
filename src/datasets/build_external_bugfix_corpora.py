from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.datasets.bugfix_corpus_schema import BugFixRecord, should_include_record


TARGETS = ("humaneval", "mbpp", "quixbugs", "repair")


def normalize_record(item: dict, source_path: str) -> BugFixRecord:
    if "source_dataset" in item:
        return BugFixRecord(**item)

    source_name = item.get("source") or os.path.basename(source_path).replace(".jsonl", "")
    metadata = item.get("metadata", {})
    if not metadata:
        metadata = {
            "scope": "function",
            "files_changed": 1,
            "changed_lines": 0,
            "has_repro": bool(item.get("tests") or item.get("failure_signal")),
            "synthetic": False,
            "generated": False,
            "framework_heavy": False,
            "non_code_fix_only": False,
        }

    return BugFixRecord(
        id=item["id"],
        source_dataset=source_name,
        source_split=item.get("source_split", "train"),
        language=item.get("language", "python"),
        task_family=item.get("task_family", "general_python"),
        repository=item.get("repository", source_name),
        instance_id=item.get("instance_id", item["id"]),
        buggy_code=item["buggy_code"],
        fixed_code=item["fixed_code"],
        file_path=item.get("file_path", ""),
        function_name=item.get("function_name", ""),
        prompt=item.get("prompt", ""),
        bug_type=item.get("bug_type", "unknown"),
        failure_signal=item.get("failure_signal", ""),
        tests=item.get("tests", []),
        commit_buggy=item.get("commit_buggy", ""),
        commit_fixed=item.get("commit_fixed", ""),
        metadata=metadata,
    )


def load_records(source_paths: list[str]) -> list[BugFixRecord]:
    records: list[BugFixRecord] = []
    for path in source_paths:
        with open(path) as handle:
            for line in handle:
                item = json.loads(line)
                records.append(normalize_record(item, path))
    return records


def dedupe_records(records: list[BugFixRecord]) -> list[BugFixRecord]:
    seen: set[tuple[str, str]] = set()
    deduped: list[BugFixRecord] = []

    for record in records:
        key = (
            " ".join(record.buggy_code.split()),
            " ".join(record.fixed_code.split()),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)

    return deduped


def build_target_corpus(
    records: list[BugFixRecord],
    target: str,
) -> tuple[list[dict], Counter]:
    effective_target = "quixbugs" if target == "repair" else target
    kept: list[dict] = []
    stats: Counter = Counter()

    for record in records:
        include, reason = should_include_record(record, target_benchmark=effective_target)
        if include:
            kept.append(record.to_retrieval_json())
            stats["included"] += 1
            stats[f"source:{record.source_dataset}"] += 1
        else:
            stats[f"excluded:{reason}"] += 1

    return kept, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-jsonl",
        action="append",
        required=True,
        help="Normalized source JSONL. Pass multiple times for multiple corpora.",
    )
    parser.add_argument("--output-dir", default="data/corpora")
    parser.add_argument(
        "--targets",
        nargs="+",
        default=list(TARGETS),
        choices=list(TARGETS),
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    records = dedupe_records(load_records(args.source_jsonl))
    print(f"Loaded {len(records)} normalized bug-fix records.")

    for target in args.targets:
        corpus, stats = build_target_corpus(records, target)
        output_path = os.path.join(args.output_dir, f"{target}_external_bugfix.jsonl")

        with open(output_path, "w") as handle:
            for item in corpus:
                handle.write(json.dumps(item) + "\n")

        summary = {
            "target": target,
            "output_path": output_path,
            "count": len(corpus),
            "stats": dict(stats),
        }
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
