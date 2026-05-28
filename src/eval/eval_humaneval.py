import argparse
import json
import os
import importlib.util
import traceback
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.humaneval_generator_baseline import generate_code_baseline
from src.models.humaneval_generator_rag import generate_code_with_rag

HUMANEVAL_PREAMBLE = (
    "from typing import *\n"
    "import math\n"
    "import re\n"
    "import itertools\n"
    "import collections\n"
    "import heapq\n"
    "import bisect\n"
    "import functools\n"
    "import random\n"
    "import statistics\n"
)


# ============================================================
# Load HumanEval dataset (YOUR format)
# ============================================================
def load_humaneval(path):
    tasks = []
    with open(path) as f:
        for line in f:
            tasks.append(json.loads(line))
    return tasks


def load_existing_results(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path) as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
    except Exception:
        traceback.print_exc()
    return []


def save_results(path: str, results: list[dict]) -> None:
    with open(path, "w") as handle:
        json.dump(results, handle, indent=2)


# ============================================================
# Save model code to temp file & import it
# ============================================================
def load_module_from_code(prompt: str, code: str):
    temp_file = "temp_candidate.py"
    with open(temp_file, "w") as f:
        f.write(HUMANEVAL_PREAMBLE)
        f.write("\n")
        f.write(prompt)
        f.write("\n")
        f.write(code)

    spec = importlib.util.spec_from_file_location("temp_candidate", temp_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules["temp_candidate"] = module

    try:
        spec.loader.exec_module(module)
        return module, True
    except Exception:
        print("[IMPORT ERROR]")
        traceback.print_exc()
        return None, False


# ============================================================
# RUN check(candidate)
# ============================================================
def run_check(module, test_code: str, func_name: str):
    test_namespace = {}

    # load check()
    try:
        exec(test_code, test_namespace)
    except Exception:
        print("[TEST LOAD ERROR]")
        traceback.print_exc()
        return False

    check_fn = test_namespace.get("check")
    if check_fn is None:
        print("[ERROR] check() not found in test code")
        return False

    if not hasattr(module, func_name):
        print(f"[MISSING FUNCTION] {func_name}")
        return False

    candidate_fn = getattr(module, func_name)

    try:
        check_fn(candidate_fn)
        return True
    except Exception:
        print("[TEST FAILURE]")
        traceback.print_exc()
        return False


# ============================================================
# BASELINE evaluation
# ============================================================
def evaluate_baseline(
    input_path="data/humaneval/HumanEval.jsonl",
    out_path="experiments/humaneval_baseline.json",
    model=None,
    limit=None,
):
    os.makedirs("experiments", exist_ok=True)
    tasks = load_humaneval(input_path)
    if limit:
        tasks = tasks[:limit]
    results = load_existing_results(out_path)
    completed = {item["task_id"] for item in results}

    print(f"\n=== BASELINE EVALUATION on {len(tasks)} tasks ===")

    for task in tasks:
        tid = task["task_id"]
        if tid in completed:
            continue
        prompt = task["prompt"]
        func_name = task["entry_point"]
        test_code = task["test"]

        print(f"\n=== BASELINE TASK {tid} ===")

        # 1. Generate code
        try:
            code = generate_code_baseline(prompt, model=model)
        except Exception as exc:
            print("[BASELINE GENERATION ERROR]", exc)
            traceback.print_exc()
            results.append({"task_id": tid, "pass": False})
            completed.add(tid)
            save_results(out_path, results)
            continue

        # 2. Load module
        module, ok = load_module_from_code(prompt, code)
        if not ok:
            print("FAIL (import error)")
            results.append({"task_id": tid, "pass": False})
            completed.add(tid)
            save_results(out_path, results)
            continue

        # 3. Run check(candidate)
        passed = run_check(module, test_code, func_name)
        print("PASS" if passed else "FAIL")

        results.append({"task_id": tid, "pass": passed})
        completed.add(tid)
        save_results(out_path, results)

    # save results
    save_results(out_path, results)

    print("\nSaved baseline results to", out_path)


# ============================================================
# RAG evaluation
# ============================================================
def evaluate_rag(
    input_path="data/humaneval/HumanEval.jsonl",
    out_path="experiments/humaneval_rag.json",
    model=None,
    limit=None,
    retrieval_profile=None,
    index_dir=None,
):
    os.makedirs("experiments", exist_ok=True)
    tasks = load_humaneval(input_path)
    if limit:
        tasks = tasks[:limit]
    results = load_existing_results(out_path)
    completed = {item["task_id"] for item in results}

    print(f"\n=== RAG EVALUATION on {len(tasks)} tasks ===")

    for task in tasks:
        tid = task["task_id"]
        if tid in completed:
            continue
        prompt = task["prompt"]
        func_name = task["entry_point"]
        test_code = task["test"]

        print(f"\n=== RAG TASK {tid} ===")

        # 1. Generate code
        # code = generate_code_with_rag(prompt)
        try:
            code = generate_code_with_rag(
                prompt,
                force_rag=True,
                model=model,
                retrieval_profile=retrieval_profile,
                index_dir=index_dir,
            )
        except Exception as exc:
            print("[RAG GENERATION ERROR]", exc)
            traceback.print_exc()
            results.append({"task_id": tid, "pass": False})
            completed.add(tid)
            save_results(out_path, results)
            continue
        # 2. Load module
        module, ok = load_module_from_code(prompt, code)
        if not ok:
            print("FAIL (import error)")
            results.append({"task_id": tid, "pass": False})
            completed.add(tid)
            save_results(out_path, results)
            continue

        # 3. Run check(candidate)
        passed = run_check(module, test_code, func_name)
        print("PASS" if passed else "FAIL")

        results.append({"task_id": tid, "pass": passed})
        completed.add(tid)
        save_results(out_path, results)

    # save results
    save_results(out_path, results)

    print("\nSaved RAG results to", out_path)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "rag"], default="rag")
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--input-path", default="data/humaneval/HumanEval.jsonl")
    parser.add_argument("--out-path", default=None)
    parser.add_argument("--retrieval-profile", default=None)
    parser.add_argument("--retrieval-index-dir", default=None)
    args = parser.parse_args()

    out_path = args.out_path or f"experiments/humaneval_{args.mode}.json"
    if args.mode == "baseline":
        evaluate_baseline(
            input_path=args.input_path,
            out_path=out_path,
            model=args.model,
            limit=args.limit,
        )
    else:
        evaluate_rag(
            input_path=args.input_path,
            out_path=out_path,
            model=args.model,
            limit=args.limit,
            retrieval_profile=args.retrieval_profile or "humaneval_clean",
            index_dir=args.retrieval_index_dir,
        )
