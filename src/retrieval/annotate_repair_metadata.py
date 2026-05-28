from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.retrieval.repair_metadata import infer_repair_metadata


def annotate_corpus(input_path: Path, output_path: Path) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with input_path.open() as source, output_path.open("w") as sink:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            record["repair_metadata"] = infer_repair_metadata(record)
            sink.write(json.dumps(record) + "\n")
            total += 1
    return {"input": str(input_path), "output": str(output_path), "records": total}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/corpora/repair_external_bugfix.jsonl")
    parser.add_argument("--output", default="data/corpora/repair_external_bugfix_annotated.jsonl")
    args = parser.parse_args()
    summary = annotate_corpus(Path(args.input), Path(args.output))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
