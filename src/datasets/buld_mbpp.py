import os
import json
from datasets import load_dataset

# -----------------------------
# Ensure output directory exists
# -----------------------------
OUT_DIR = os.path.join("data", "mbpp")
os.makedirs(OUT_DIR, exist_ok=True)   # <-- fixes FileNotFoundError

OUT = os.path.join(OUT_DIR, "mbpp_correct.jsonl")

# -----------------------------
# Load MBPP dataset
# -----------------------------
mbpp = load_dataset("mbpp", "full")

# -----------------------------
# Write JSONL file
# -----------------------------
with open(OUT, "w") as f:
    for item in mbpp["train"]:
        f.write(json.dumps({
            "id": item["task_id"],
            "prompt": item["text"],
            "correct_code": item["code"],
            "tests": item["test_list"]
        }) + "\n")

print(f"Saved MBPP correct solutions to: {OUT}")
