from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


DEFAULT_INPUT = "data/indexes/repair_clean/meta.jsonl"
DEFAULT_OUTPUT_DIR = "data/corpora"


def normalize_project_name(value: str | None) -> str:
    if not value:
        return ""
    leaf = value.split("/")[-1]
    return re.sub(r"[^a-z0-9]+", "", leaf.lower())


def project_aliases(projects: list[str]) -> set[str]:
    aliases = {normalize_project_name(project) for project in projects}
    # PyBugHive uses spaCy while BugsInPy uses spacy in ids.
    if "spacy" in aliases:
        aliases.add("spacy")
    return {alias for alias in aliases if alias}


def candidate_project_keys(item: dict[str, Any]) -> set[str]:
    keys: set[str] = set()

    repository = item.get("repository")
    if isinstance(repository, str):
        keys.add(normalize_project_name(repository))

    item_id = item.get("id")
    if isinstance(item_id, str):
        parts = item_id.split(":")
        if len(parts) >= 2:
            keys.add(normalize_project_name(parts[1]))

    instance_id = item.get("instance_id")
    if isinstance(instance_id, str):
        parts = re.split(r"[:_]", instance_id)
        if len(parts) >= 2 and parts[0].lower() == "bugsinpy":
            keys.add(normalize_project_name(parts[1]))

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for field in ("project", "repository", "repo"):
            value = metadata.get(field)
            if isinstance(value, str):
                keys.add(normalize_project_name(value))

    return {key for key in keys if key}


def read_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return rows


def write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def filter_rows(
    rows: list[dict[str, Any]],
    excluded_projects: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    excluded_keys = project_aliases(excluded_projects)
    kept: list[dict[str, Any]] = []
    removed_by_project: Counter[str] = Counter()

    for row in rows:
        matching_keys = candidate_project_keys(row) & excluded_keys
        if matching_keys:
            for key in sorted(matching_keys):
                removed_by_project[key] += 1
            continue
        kept.append(row)

    summary = {
        "input_count": len(rows),
        "kept_count": len(kept),
        "removed_count": len(rows) - len(kept),
        "excluded_projects": excluded_projects,
        "excluded_project_keys": sorted(excluded_keys),
        "removed_by_project": dict(sorted(removed_by_project.items())),
    }
    return kept, summary


def default_output_path(projects: list[str]) -> str:
    slug = "_".join(normalize_project_name(project) for project in projects)
    return os.path.join(DEFAULT_OUTPUT_DIR, f"repair_clean_holdout_{slug}.jsonl")


def maybe_build_index(input_path: str, profile: str) -> None:
    from src.retrieval.build_index import build_index

    build_index(input_path=input_path, profile=profile)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a repair corpus with selected project families removed."
    )
    parser.add_argument("--input-path", default=DEFAULT_INPUT)
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--exclude-projects", nargs="+", required=True)
    parser.add_argument("--summary-path", default=None)
    parser.add_argument(
        "--build-index",
        action="store_true",
        help="Build a FAISS retrieval profile from the filtered corpus.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Retrieval profile name to build when --build-index is set.",
    )
    args = parser.parse_args()

    output_path = args.output_path or default_output_path(args.exclude_projects)
    rows = read_jsonl(args.input_path)
    kept, summary = filter_rows(rows, args.exclude_projects)
    summary.update(
        {
            "input_path": args.input_path,
            "output_path": output_path,
            "profile": args.profile,
        }
    )
    write_jsonl(output_path, kept)

    summary_path = args.summary_path or f"{output_path}.summary.json"
    os.makedirs(os.path.dirname(summary_path) or ".", exist_ok=True)
    with open(summary_path, "w") as handle:
        json.dump(summary, handle, indent=2)

    print(json.dumps(summary, indent=2))

    if args.build_index:
        if not args.profile:
            raise SystemExit("--profile is required with --build-index")
        maybe_build_index(output_path, args.profile)


if __name__ == "__main__":
    main()
