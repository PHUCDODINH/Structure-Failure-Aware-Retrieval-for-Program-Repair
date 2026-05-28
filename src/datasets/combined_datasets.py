import json

OUT = "data/all_bugfix_pairs.jsonl"

paths = [
    "data/quixbugs/quixbugs_bugfix.jsonl",
    "data/mbpp/mbpp_bugfix.jsonl"
]

with open(OUT, "w") as fout:
    for path in paths:
        with open(path) as f:
            for line in f:
                fout.write(line)

print(f"Combined dataset saved → {OUT}")
