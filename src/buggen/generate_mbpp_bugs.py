import os
import json
import random
import re

INPUT = "data/mbpp/mbpp_correct.jsonl"
OUT_DIR = "data/mbpp"
os.makedirs(OUT_DIR, exist_ok=True)

OUTPUT = os.path.join(OUT_DIR, "mbpp_bugfix.jsonl")

# -------------------------
# Bug mutation functions
# -------------------------

def mutate_operator(code):
    # + → -, * → //
    if "+" in code:
        return code.replace("+", "-", 1)
    if "*" in code:
        return code.replace("*", "//", 1)
    return None

def mutate_off_by_one(code):
    # range(n) → range(n-1) or range(1, n)
    if "range(" in code:
        return code.replace("range(", "range(1,", 1)
    return None

def mutate_variable(code):
    # Replace the first variable with 'x'
    return re.sub(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", "x", code, count=1)

def mutate_return(code):
    # Remove the return statement (simple bug)
    return re.sub(r"return .+", "pass  # BUG: removed return", code)

BUG_FUNCTIONS = [
    mutate_operator,
    mutate_off_by_one,
    mutate_variable,
    mutate_return
]

# -------------------------
# Apply mutations
# -------------------------

with open(INPUT) as f_in, open(OUTPUT, "w") as fout:
    for line in f_in:
        item = json.loads(line)
        correct = item["correct_code"]
        prompt = item["prompt"]
        tests = item["tests"]

        for func in BUG_FUNCTIONS:
            buggy = func(correct)
            if not buggy or buggy == correct:
                continue

            record = {
                "id": f"{item['id']}_{func.__name__}",
                "source": "mbpp_synthetic",
                "prompt": prompt,
                "buggy_code": buggy,
                "fixed_code": correct,
                "tests": tests,
                "bug_type": func.__name__
            }

            fout.write(json.dumps(record) + "\n")

print(f"Saved synthetic MBPP bug-fix pairs → {OUTPUT}")
