from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from pathlib import Path
from urllib.request import urlopen


DEFAULT_URL = (
    "https://raw.githubusercontent.com/bigcode-project/octopack/main/"
    "evaluation/create/humaneval-x/data/python/data/humanevalpack.jsonl"
)
DEFAULT_OUT = "data/humanevalfix/HumanEvalFix.jsonl"


REQUIRED_FIELDS = {
    "task_id",
    "canonical_solution",
    "buggy_solution",
    "test",
    "entry_point",
    "bug_type",
    "failure_symptoms",
}


def read_jsonl_text_from_url(url: str, allow_insecure_ssl: bool = False) -> str:
    context = ssl._create_unverified_context() if allow_insecure_ssl else None
    with urlopen(url, timeout=60, context=context) as response:
        return response.read().decode("utf-8")


def read_jsonl_text(path_or_url: str, allow_insecure_ssl: bool = False) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return read_jsonl_text_from_url(path_or_url, allow_insecure_ssl=allow_insecure_ssl)
    return Path(path_or_url).read_text()


def normalize_row(row: dict, source_url: str) -> dict:
    missing = sorted(field for field in REQUIRED_FIELDS if field not in row)
    if missing:
        raise ValueError(f"{row.get('task_id', '<unknown>')} missing fields: {missing}")

    declaration = row.get("declaration") or row.get("prompt") or ""
    prompt = row.get("prompt") or declaration
    buggy_code_tests = declaration + row["buggy_solution"]
    fixed_code_tests = declaration + row["canonical_solution"]
    buggy_code_docs = prompt + row["buggy_solution"]
    fixed_code_docs = prompt + row["canonical_solution"]

    return {
        "task_id": row["task_id"],
        "entry_point": row["entry_point"],
        "bug_type": row["bug_type"],
        "failure_symptoms": row["failure_symptoms"],
        "prompt": prompt,
        "declaration": declaration,
        "buggy_solution": row["buggy_solution"],
        "canonical_solution": row["canonical_solution"],
        "buggy_code_tests": buggy_code_tests,
        "fixed_code_tests": fixed_code_tests,
        "buggy_code_docs": buggy_code_docs,
        "fixed_code_docs": fixed_code_docs,
        "test": row["test"],
        "example_test": row.get("example_test", ""),
        "signature": row.get("signature", ""),
        "docstring": row.get("docstring", ""),
        "instruction": row.get("instruction", ""),
        "source_dataset": "bigcode/humanevalpack",
        "source_task": "humanevalfix-python",
        "source_url": source_url,
    }


def import_humanevalfix(
    input_path_or_url: str,
    output_path: str,
    allow_insecure_ssl: bool = False,
) -> list[dict]:
    raw_text = read_jsonl_text(input_path_or_url, allow_insecure_ssl=allow_insecure_ssl)
    rows: list[dict] = []
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_no}: {exc}") from exc
        rows.append(normalize_row(row, source_url=input_path_or_url))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    summary = {
        "output_path": output_path,
        "rows": len(rows),
        "source": input_path_or_url,
        "task_ids": [row["task_id"] for row in rows[:5]],
    }
    print(json.dumps(summary, indent=2))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Import BigCode HumanEvalFix Python data.")
    parser.add_argument("--input", default=DEFAULT_URL, help="Source JSONL path or URL.")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--allow-insecure-ssl",
        action="store_true",
        help="Disable TLS certificate verification for this download only.",
    )
    args = parser.parse_args()
    import_humanevalfix(
        input_path_or_url=args.input,
        output_path=args.out,
        allow_insecure_ssl=args.allow_insecure_ssl,
    )


if __name__ == "__main__":
    main()
