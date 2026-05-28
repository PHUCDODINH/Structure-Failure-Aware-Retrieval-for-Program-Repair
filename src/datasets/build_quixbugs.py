import os
import json

BASE = "data/quixbugs"
os.makedirs(BASE, exist_ok=True)   # ← FIX HERE

# NOTE: The QuixBugs source dataset has BACKWARDS directory names!
# - The "buggy" folder actually contains CORRECT code
# - The "correct" folder actually contains BUGGY code  
# So we swap them here to get the right labels
BUGGY_DIR = os.path.join(BASE, "correct")  # Contains buggy code despite name
CORRECT_DIR = os.path.join(BASE, "buggy")  # Contains correct code despite name
OUT_PATH = os.path.join(BASE, "quixbugs_bugfix.jsonl")

with open(OUT_PATH, "w") as fout:
    for fname in os.listdir(BUGGY_DIR):
        if not fname.endswith(".py"):
            continue

        buggy_path = os.path.join(BUGGY_DIR, fname)
        correct_path = os.path.join(CORRECT_DIR, fname)

        if not os.path.exists(correct_path):
            continue

        with open(buggy_path, "r") as f:
            buggy = f.read()
        with open(correct_path, "r") as f:
            fixed = f.read()

        record = {
            "id": fname.replace(".py", ""),
            "source": "quixbugs",
            "buggy_code": buggy,
            "fixed_code": fixed,
            "bug_type": "unknown"
        }

        fout.write(json.dumps(record) + "\n")

print("DONE → Saved:", OUT_PATH)
