import argparse
import json
import traceback
import importlib.util
import sys
import os
import signal
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# -----------------------------
# Generators
# -----------------------------
from src.models.humaneval_generator_rag import generate_code_with_rag
from src.models.humaneval_generator_baseline import generate_code_baseline

# -----------------------------
# Test parser (assert + Pair)
# -----------------------------
import re
import ast
import inspect

PAIR_PATTERN = re.compile(r"Pair\((\d+),\s*(\d+)\)")
TEST_TIMEOUT_SECONDS = int(os.getenv("MBPP_TEST_TIMEOUT_SECONDS", "2"))


def convert_pairs(expr: str):
    """
    Converts 'Pair(a,b)' into ('PAIR', a, b).
    This lets us later reconstruct Pair objects before calling the function.
    """
    def repl(match):
        a = int(match.group(1))
        b = int(match.group(2))
        return f"('PAIR', {a}, {b})"

    return PAIR_PATTERN.sub(repl, expr)


def safe_parse_tests(raw_tests):
    """
    Parse MBPP tests like:
    ["assert f([Pair(5,6)], 4) == 3", ...]
    into standardized format:
        [{"input": [...], "output": ...}]
    """
    parsed = []

    for line in raw_tests:
        line = line.strip()
        if not line.startswith("assert"):
            continue

        try:
            # Remove "assert "
            expr = line[len("assert "):]

            # Split at ==
            left, right = expr.split("==")
            left = left.strip()
            right = right.strip()

            # Convert right-hand expected result
            expected = ast.literal_eval(convert_pairs(right))

            # Extract arguments inside function call: f(...)
            inside = left[left.index("(") + 1: left.rindex(")")]

            # Convert Pair calls inside to safe tuples
            inside = convert_pairs(inside)

            # Turn argument list into python list
            inputs = ast.literal_eval(f"[{inside}]")

            parsed.append({"input": inputs, "output": expected})

        except Exception as e:
            print("[TEST PARSE ERROR]", line)
            print(e)

    return parsed


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


def extract_mbpp_call_metadata(raw_tests):
    """
    Infer the target function name, arity, and a few concrete behavior examples
    from the visible MBPP asserts.
    """
    function_name = None
    examples = []
    arities = []
    pair_like_inputs = False

    for line in raw_tests:
        line = line.strip()
        if not line.startswith("assert"):
            continue

        try:
            expr = line[len("assert "):]
            left, right = expr.split("==", 1)
            left = left.strip()
            right = right.strip()

            call_expr = ast.parse(convert_pairs(left), mode="eval").body
            if not isinstance(call_expr, ast.Call):
                continue

            if isinstance(call_expr.func, ast.Name):
                function_name = function_name or call_expr.func.id

            rendered_args = []
            for arg in call_expr.args:
                rendered = ast.unparse(arg)
                rendered_args.append(rendered)
                if "PAIR" in rendered:
                    pair_like_inputs = True

            arities.append(len(rendered_args))
            example_call = f"solution({', '.join(rendered_args)})"
            examples.append(f"{example_call} == {right}")
        except Exception as exc:
            print("[CONTRACT PARSE ERROR]", line)
            print(exc)

    arity = arities[0] if arities else None
    if arities and any(value != arity for value in arities):
        arity = None

    return {
        "function_name": function_name,
        "arity": arity,
        "examples": examples[:3],
        "pair_like_inputs": pair_like_inputs,
    }


def build_mbpp_generation_prompt(prompt: str, contract: dict) -> str:
    param_count = contract.get("arity")
    if param_count is None or param_count <= 0:
        signature = "def solution(*args):"
    else:
        params = ", ".join(f"arg{i + 1}" for i in range(param_count))
        signature = f"def solution({params}):"

    contract_lines = [
        "Write ONLY Python code.",
        "Define EXACTLY one top-level function named `solution`.",
        f"Required signature: `{signature}`",
        "Do NOT add comments or explanations.",
    ]

    original_name = contract.get("function_name")
    if original_name:
        contract_lines.append(
            f"The original benchmark refers to this behavior as `{original_name}`, "
            "but your output function must still be named `solution`."
        )

    if contract.get("pair_like_inputs"):
        contract_lines.append(
            "Some inputs may contain Pair-like objects with `.a` and `.b` attributes."
        )

    examples = contract.get("examples") or []
    if examples:
        contract_lines.append("Behavior examples:")
        contract_lines.extend(f"- {example}" for example in examples)

    return (
        "\n".join(contract_lines)
        + "\n\n"
        + "Problem:\n"
        + f"{prompt}\n\n"
        + f"{signature}\n"
    )


# =========================================================
# Reconstruct Pair objects BEFORE calling student's function
# =========================================================
class Pair:
    def __init__(self, a, b):
        self.a = a
        self.b = b


def reconstruct(value):
    """
    Convert ('PAIR', a, b) → Pair(a,b)
    Recursively reconstruct lists.
    """
    if isinstance(value, tuple) and value and value[0] == "PAIR":
        return Pair(value[1], value[2])

    if isinstance(value, list):
        return [reconstruct(v) for v in value]

    return value


# =========================================================
# Utility — Load Generated Code
# =========================================================
def load_code_as_function(code: str, preferred_name="solution", fallback_name=None):
    temp_path = "temp_mbpp_gen.py"

    with open(temp_path, "w") as f:
        f.write(code)

    spec = importlib.util.spec_from_file_location("temp_mbpp_gen", temp_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["temp_mbpp_gen"] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print("[IMPORT ERROR]", e)
        traceback.print_exc()
        return None

    if hasattr(module, preferred_name):
        return getattr(module, preferred_name)

    if fallback_name and hasattr(module, fallback_name):
        return getattr(module, fallback_name)

    functions = [
        value
        for _, value in inspect.getmembers(module, inspect.isfunction)
        if value.__module__ == "temp_mbpp_gen"
    ]
    if functions:
        return min(functions, key=lambda fn: fn.__code__.co_firstlineno)

    print("[ERROR] No callable function found in generated module.")
    return None

# =========================================================
# Run MBPP Tests
# =========================================================
def run_tests(func, tests):
    def _handle_timeout(signum, frame):
        raise TimeoutError(f"Test execution exceeded {TEST_TIMEOUT_SECONDS}s")

    for t in tests:
        previous_handler = None
        try:
            inp = reconstruct(t["input"])
            expected = t["output"]

            previous_handler = signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(TEST_TIMEOUT_SECONDS)
            if isinstance(inp, list):
                result = func(*inp)
            else:
                result = func(inp)
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)

            if result != expected:
                print(f"[FAIL] input={inp}, expected={expected}, got={result}")
                return False

        except Exception as e:
            signal.alarm(0)
            if previous_handler is not None:
                signal.signal(signal.SIGALRM, previous_handler)
            print("[RUNTIME ERROR]", e)
            traceback.print_exc()
            return False

    return True


# =========================================================
# RAG Evaluation
# =========================================================
def evaluate_mbpp(
    mbpp_path="data/mbpp/mbpp_correct.jsonl",
    results_path="experiments/mbpp_gen_results.json",
    limit=None,
    model=None,
    retrieval_profile=None,
    index_dir=None,
):
    results = load_existing_results(results_path)

    with open(mbpp_path) as f:
        tasks = [json.loads(l) for l in f]

    if limit:
        tasks = tasks[:limit]

    print(f"\n=== Evaluating {len(tasks)} MBPP Tasks (RAG) ===\n")

    os.makedirs("experiments", exist_ok=True)
    completed = {item["id"] for item in results}

    for item in tasks:
        tid = item["id"]
        if tid in completed:
            continue
        tests = safe_parse_tests(item["tests"])
        contract = extract_mbpp_call_metadata(item["tests"])
        prompt = build_mbpp_generation_prompt(item["prompt"], contract)
        print(f"\n[RAG] Task {tid}: parsed {len(tests)} tests.")

        try:
            generated = generate_code_with_rag(
                prompt,
                k=5,
                model=model,
                retrieval_profile=retrieval_profile,
                index_dir=index_dir,
            )
        except Exception as e:
            print("[RAG GENERATION ERROR]", e)
            traceback.print_exc()
            results.append({"id": tid, "pass": False})
            completed.add(tid)
            save_results(results_path, results)
            continue

        func = load_code_as_function(
            generated,
            fallback_name=contract.get("function_name"),
        )
        if func is None:
            results.append({"id": tid, "pass": False})
            completed.add(tid)
            save_results(results_path, results)
            continue

        passed = run_tests(func, tests)
        print("PASS" if passed else "FAIL")

        results.append({"id": tid, "pass": passed})
        completed.add(tid)
        save_results(results_path, results)

    print("\nSaved RAG results to:", results_path)
    return results


# =========================================================
# BASELINE Evaluation
# =========================================================
def evaluate_mbpp_baseline(
    mbpp_path="data/mbpp/mbpp_correct.jsonl",
    results_path="experiments/mbpp_baseline_results.json",
    limit=None,
    model=None
):
    results = load_existing_results(results_path)

    with open(mbpp_path) as f:
        tasks = [json.loads(l) for l in f]

    if limit:
        tasks = tasks[:limit]

    print(f"\n=== Evaluating {len(tasks)} MBPP Tasks (Baseline) ===\n")

    os.makedirs("experiments", exist_ok=True)
    completed = {item["id"] for item in results}

    for item in tasks:
        tid = item["id"]
        if tid in completed:
            continue
        tests = safe_parse_tests(item["tests"])
        contract = extract_mbpp_call_metadata(item["tests"])
        prompt = build_mbpp_generation_prompt(item["prompt"], contract)
        print(f"\n[BASELINE] Task {tid}: parsed {len(tests)} tests.")

        try:
            generated = generate_code_baseline(prompt, model=model)
        except Exception as e:
            print("[BASELINE GEN ERROR]", e)
            traceback.print_exc()
            results.append({"id": tid, "pass": False})
            completed.add(tid)
            save_results(results_path, results)
            continue

        func = load_code_as_function(
            generated,
            fallback_name=contract.get("function_name"),
        )
        if func is None:
            results.append({"id": tid, "pass": False})
            completed.add(tid)
            save_results(results_path, results)
            continue

        passed = run_tests(func, tests)
        print("PASS" if passed else "FAIL")

        results.append({"id": tid, "pass": passed})
        completed.add(tid)
        save_results(results_path, results)

    print("\nSaved baseline results to:", results_path)
    return results


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "rag"], default="rag")
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mbpp-path", default="data/mbpp/mbpp_correct.jsonl")
    parser.add_argument("--results-path", default=None)
    parser.add_argument("--retrieval-profile", default=None)
    parser.add_argument("--retrieval-index-dir", default=None)
    args = parser.parse_args()

    default_results = (
        "experiments/mbpp_baseline_results.json"
        if args.mode == "baseline"
        else "experiments/mbpp_gen_results.json"
    )
    results_path = args.results_path or default_results

    if args.mode == "baseline":
        evaluate_mbpp_baseline(
            mbpp_path=args.mbpp_path,
            results_path=results_path,
            limit=args.limit,
            model=args.model,
        )
    else:
        evaluate_mbpp(
            mbpp_path=args.mbpp_path,
            results_path=results_path,
            limit=args.limit,
            model=args.model,
            retrieval_profile=args.retrieval_profile or "mbpp_clean",
            index_dir=args.retrieval_index_dir,
        )
