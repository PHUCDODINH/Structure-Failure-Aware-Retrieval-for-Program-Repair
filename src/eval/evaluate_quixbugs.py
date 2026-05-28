import argparse
import os
import sys
import json
import re
import subprocess
import traceback
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.repair_baseline import repair_without_rag
from src.models.repair_rag import repair_with_rag
from src.retrieval.failure_state import make_failure_state


BUGGY_DIR = "data/quixbugs/buggy"
ALT_BUGGY_DIR = "data/quixbugs/correct"
TEST_DIR = "data/quixbugs/test"
PYTEST_TIMEOUT_SECONDS = int(os.getenv("QUIXBUGS_PYTEST_TIMEOUT_SECONDS", "10"))
USE_FAILURE_SIGNAL_BY_DEFAULT = os.getenv("QUIXBUGS_USE_FAILURE_SIGNAL", "0") == "1"
DEFAULT_RAG_MAX_ATTEMPTS = int(os.getenv("QUIXBUGS_RAG_MAX_ATTEMPTS", "1"))
DEFAULT_RAG_CANDIDATES = int(os.getenv("QUIXBUGS_RAG_CANDIDATES", "1"))
PYTEST_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors)")


class InfrastructureFailure(Exception):
    pass


# ============================================================
# AUTODETECT PROBLEMS
# ============================================================
def autodetect_problems():
    """
    Detect REAL QuixBugs problems automatically.
    Steps:
    - List buggy/*.py
    - Skip *_test.py
    - Check if a test_<problem>.py exists
    """

    buggy_files = sorted(
        f for f in os.listdir(BUGGY_DIR)
        if f.endswith(".py") and not f.endswith("_test.py")
    )

    problems = []
    for fname in buggy_files:
        problem = fname[:-3]  # strip .py

        # Try matching test file
        test1 = os.path.join(TEST_DIR, f"test_{problem}.py")

        # Some buggy files have unexpected "_test" suffixes
        problem_clean = problem.replace("_test", "")
        test2 = os.path.join(TEST_DIR, f"test_{problem_clean}.py")

        if os.path.exists(test1):
            problems.append(problem)
        elif os.path.exists(test2):
            problems.append(problem)
        else:
            print(f"[SKIP] No test file for {problem}")

    return problems


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


def write_trace(
    trace_dir: str | None,
    mode: str,
    problem: str,
    attempt: int,
    payload: dict,
) -> None:
    if not trace_dir:
        return
    os.makedirs(trace_dir, exist_ok=True)
    trace_path = os.path.join(trace_dir, f"{mode}__{problem}__attempt{attempt}.json")
    with open(trace_path, "w") as handle:
        json.dump(payload, handle, indent=2)


# ============================================================
# Write repaired code into temp_quixbugs structure
# ============================================================
def write_temp_buggy(problem, repaired_code):
    temp_root = "temp_quixbugs"
    buggy_path = os.path.join(temp_root, "data", "quixbugs", "buggy")

    for p in [
        temp_root,
        os.path.join(temp_root, "data"),
        os.path.join(temp_root, "data", "quixbugs"),
        buggy_path,
    ]:
        os.makedirs(p, exist_ok=True)
        init = os.path.join(p, "__init__.py")
        if not os.path.exists(init):
            with open(init, "w") as f:
                f.write("")

    out_file = os.path.join(buggy_path, f"{problem}.py")
    with open(out_file, "w") as f:
        f.write(repaired_code)

    return os.path.abspath(temp_root)


def summarize_failure_output(stdout: str, stderr: str, max_lines: int = 40) -> str:
    lines: list[str] = []
    for source in (stdout, stderr):
        for line in source.splitlines():
            stripped = line.rstrip()
            if not stripped:
                continue
            if stripped.startswith(("==", "--")):
                continue
            lines.append(stripped)

    if not lines:
        return ""

    clipped = lines[:max_lines]
    return "\n".join(clipped)


def extract_pytest_counts(stdout: str, stderr: str) -> tuple[int, int]:
    passed = 0
    failed = 0
    for source in (stdout, stderr):
        for count_text, label in PYTEST_COUNT_RE.findall(source):
            count = int(count_text)
            if label == "passed":
                passed = max(passed, count)
            else:
                failed = max(failed, count)
    return passed, failed


def execution_score(stdout: str, stderr: str) -> dict:
    passed_tests, failed_tests = extract_pytest_counts(stdout, stderr)
    diagnostic_text = f"{stdout}\n{stderr}"
    penalty = 0
    for token, weight in (
        ("SyntaxError", 4),
        ("IndentationError", 4),
        ("NameError", 3),
        ("ImportError", 3),
        ("AttributeError", 2),
        ("TypeError", 2),
    ):
        if token in diagnostic_text:
            penalty += weight

    return {
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "penalty": penalty,
        "summary": summarize_failure_output(stdout, stderr),
    }


def candidate_sort_key(candidate: dict) -> tuple[int, int, int, int]:
    return (
        1 if candidate["pass"] else 0,
        candidate.get("passed_tests", 0),
        -candidate.get("failed_tests", 0),
        -candidate.get("penalty", 0),
    )


def candidate_strategy(candidate_index: int) -> tuple[str, float]:
    plans = [
        (
            "Prefer the smallest local patch that preserves the existing control flow and data structures.",
            0.0,
        ),
        (
            "Prefer fixing the failing invariant or ordering rule, even if one local block needs a slightly broader change.",
            0.2,
        ),
        (
            "Prefer a semantic repair if a tiny patch seems insufficient, but preserve the function interface and overall structure.",
            0.4,
        ),
    ]
    strategy, temperature = plans[(candidate_index - 1) % len(plans)]
    return strategy, temperature


# ============================================================
# Find test file for a given problem
# ============================================================
def find_test_file(problem):
    test1 = os.path.join(TEST_DIR, f"test_{problem}.py")

    problem_clean = problem.replace("_test", "")
    test2 = os.path.join(TEST_DIR, f"test_{problem_clean}.py")

    if os.path.exists(test1):
        return test1
    if os.path.exists(test2):
        return test2

    return None


# ============================================================
# Run pytest for one problem
# ============================================================
def run_pytest(test_path, temp_root):
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")

    env["PYTHONPATH"] = os.pathsep.join([
        temp_root,
        os.path.abspath("data/quixbugs"),
        existing
    ])
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    launcher = (
        "import pytest, sys; "
        "setattr(pytest, 'use_correct', False); "
        "setattr(pytest, 'run_slow', False); "
        "from pytest import main; "
        "sys.exit(main(sys.argv[1:]))"
    )

    cmd = [
        sys.executable,
        "-c", launcher,
        os.path.abspath(test_path),
        "-q",
        "--disable-warnings",
        "--maxfail=1",
    ]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        stderr = (
            f"{stderr}\n[PYTEST TIMEOUT] Exceeded {PYTEST_TIMEOUT_SECONDS}s while running {os.path.basename(test_path)}"
        ).strip()
        return False, stdout, stderr

    return result.returncode == 0, result.stdout, result.stderr


def collect_failure_signal(problem: str, buggy_code: str, testfile: str) -> str:
    temp_root = write_temp_buggy(problem, buggy_code)
    passed, out, err = run_pytest(testfile, temp_root)
    if passed:
        return "Original buggy code unexpectedly passed the available tests."
    summary = summarize_failure_output(out, err)
    if not summary:
        return "Tests failed, but no detailed failure output was captured."
    return (
        f"Failing test file: {os.path.basename(testfile)}\n"
        "Observed failing signal:\n"
        f"{summary}"
    )


def select_buggy_source(problem: str, testfile: str) -> dict:
    candidates: list[dict] = []
    for label, base_dir in (("buggy", BUGGY_DIR), ("correct", ALT_BUGGY_DIR)):
        path = os.path.join(base_dir, f"{problem}.py")
        if not os.path.exists(path):
            continue

        with open(path) as handle:
            code = handle.read()

        temp_root = write_temp_buggy(problem, code)
        passed, out, err = run_pytest(testfile, temp_root)
        summary = summarize_failure_output(out, err)
        candidates.append(
            {
                "label": label,
                "path": path,
                "code": code,
                "passed": passed,
                "stdout": out,
                "stderr": err,
                "summary": summary,
            }
        )

    if not candidates:
        raise FileNotFoundError(f"No source file found for problem {problem}")

    failing = [candidate for candidate in candidates if not candidate["passed"]]
    if failing:
        chosen = next((candidate for candidate in failing if candidate["label"] == "buggy"), failing[0])
        if chosen["summary"]:
            signal = (
                f"Failing test file: {os.path.basename(testfile)}\n"
                "Observed failing signal:\n"
                f"{chosen['summary']}"
            )
        else:
            signal = "Tests failed, but no detailed failure output was captured."
        chosen["failure_signal"] = signal
        return chosen

    chosen = candidates[0]
    chosen["failure_signal"] = "Original buggy code unexpectedly passed the available tests."
    return chosen


def build_followup_failure_signal(
    testfile: str,
    prior_signal: str,
    stdout: str,
    stderr: str,
) -> str:
    summary = summarize_failure_output(stdout, stderr)
    if not summary:
        summary = "The previous repair still failed, but no detailed failure output was captured."
    return (
        f"{prior_signal}\n\n"
        "The previous repair attempt still fails.\n"
        f"Failing test file: {os.path.basename(testfile)}\n"
        "New failing signal:\n"
        f"{summary}"
    )


# ============================================================
# Evaluate one problem w/ baseline or RAG
# ============================================================
def evaluate_problem(
    problem,
    repair_fn,
    mode,
    model=None,
    retrieval_profile=None,
    index_dir=None,
    trace_dir=None,
    use_failure_signal: bool = USE_FAILURE_SIGNAL_BY_DEFAULT,
    rag_max_attempts: int = DEFAULT_RAG_MAX_ATTEMPTS,
    rag_k: int = 2,
    rag_candidates: int = DEFAULT_RAG_CANDIDATES,
    retrieval_variant: str = "structured",
    disabled_components: frozenset[str] | None = None,
):
    print(f"\n=== {problem} ({mode}) ===")

    testfile = find_test_file(problem)
    if testfile is None:
        print("[ERROR] No matching test file found.")
        return False

    source = select_buggy_source(problem, testfile)
    buggy_code = source["code"]
    failure_signal = source["failure_signal"]

    current_code = buggy_code
    current_signal = failure_signal if use_failure_signal else ""
    current_failure_state = make_failure_state(current_signal, current_code).to_dict()
    max_attempts = max(1, rag_max_attempts) if mode == "rag" else 1
    if not use_failure_signal:
        max_attempts = 1

    for attempt in range(1, max_attempts + 1):
        candidate_results: list[dict] = []
        total_candidates = max(1, rag_candidates) if mode == "rag" else 1

        for candidate_index in range(1, total_candidates + 1):
            try:
                if mode == "rag":
                    strategy_note, generation_temperature = candidate_strategy(candidate_index)
                    repair_result = repair_fn(
                        current_code,
                        description=current_signal,
                        model=model,
                        k=rag_k,
                        retrieval_profile=retrieval_profile,
                        index_dir=index_dir,
                        retrieval_variant=retrieval_variant,
                        failure_state=current_failure_state,
                        generation_temperature=generation_temperature,
                        strategy_note=strategy_note,
                        return_debug=True,
                        disabled_components=disabled_components,
                    )
                else:
                    strategy_note = ""
                    generation_temperature = 0.0
                    repair_result = repair_fn(
                        current_code,
                        description=current_signal,
                        model=model,
                        return_debug=True,
                    )
            except Exception as e:
                print("[GENERATION ERROR]", e)
                traceback.print_exc()
                if e.__class__.__name__ in {"APIConnectionError", "APITimeoutError"}:
                    raise InfrastructureFailure(str(e)) from e
                return False

            repaired = repair_result["code"]
            if repair_result.get("patch_apply_status") == "rejected":
                passed = False
                out = ""
                err = f"[PATCH REJECTED]\n{repair_result.get('patch_rejection_reason') or 'unknown reason'}"
            else:
                temp_root = write_temp_buggy(problem, repaired)
                passed, out, err = run_pytest(testfile, temp_root)
            score = execution_score(out, err)
            candidate_results.append(
                {
                    "candidate_index": candidate_index,
                    "strategy_note": strategy_note,
                    "generation_temperature": generation_temperature,
                    "generated_code": repaired,
                    "pass": passed,
                    "stdout": out,
                    "stderr": err,
                    "messages": repair_result.get("messages"),
                    "prompt": repair_result.get("prompt"),
                    "retrieved_examples": repair_result.get("retrieved_examples"),
                    "retrieval_variant": repair_result.get("retrieval_variant"),
                    "retrieval_debug": repair_result.get("retrieval_debug"),
                    "failure_state": repair_result.get("failure_state") or current_failure_state,
                    "patch_schema_version": repair_result.get("patch_schema_version"),
                    "patch_validation_retries": repair_result.get("patch_validation_retries"),
                    "patch_attempts": repair_result.get("patch_attempts"),
                    "patch_raw_response": repair_result.get("patch_raw_response"),
                    "patch_edits": repair_result.get("patch_edits"),
                    "patch_apply_status": repair_result.get("patch_apply_status"),
                    "patch_applied_edits": repair_result.get("patch_applied_edits"),
                    "patch_rejection_reason": repair_result.get("patch_rejection_reason"),
                    **score,
                }
            )
        best_result = max(candidate_results, key=candidate_sort_key)
        repaired = best_result["generated_code"]
        passed = best_result["pass"]
        out = best_result["stdout"]
        err = best_result["stderr"]

        write_trace(
            trace_dir,
            mode,
            problem,
            attempt,
            {
                "problem": problem,
                "mode": mode,
                "attempt": attempt,
                "model": model,
                "test_file": os.path.basename(testfile),
                "retrieval_profile": retrieval_profile,
                "rag_k": rag_k if mode == "rag" else None,
                "rag_candidates": total_candidates if mode == "rag" else None,
                "retrieval_variant": retrieval_variant if mode == "rag" else None,
                "source_buggy_path": source["path"],
                "source_buggy_label": source["label"],
                "input_buggy_code": current_code,
                "failure_signal": failure_signal,
                "failure_state": current_failure_state,
                "prompt_description": current_signal,
                "use_failure_signal": use_failure_signal,
                "generated_code": repaired,
                "pass": passed,
                "stdout": out,
                "stderr": err,
                "passed_tests": best_result.get("passed_tests"),
                "failed_tests": best_result.get("failed_tests"),
                "penalty": best_result.get("penalty"),
                "messages": best_result.get("messages"),
                "prompt": best_result.get("prompt"),
                "retrieved_examples": best_result.get("retrieved_examples"),
                "selected_candidate_index": best_result.get("candidate_index"),
                "selected_strategy_note": best_result.get("strategy_note"),
                "candidate_results": candidate_results,
            },
        )

        if passed:
            if attempt > 1:
                print(f"PASS (attempt {attempt})")
            else:
                print("PASS")
            return True

        if attempt < max_attempts:
            print(f"[RETRY] attempt {attempt} failed, retrying with failing-test feedback.")
            current_code = repaired
            current_signal = build_followup_failure_signal(testfile, current_signal, out, err)
            current_failure_state = make_failure_state(current_signal, current_code).to_dict()
            continue

        print("FAIL")
        if out.strip():
            print("---- STDOUT ----")
            print(out)
        if err.strip():
            print("---- STDERR ----")
            print(err)
        return False

    return False


# ============================================================
# Evaluate ALL Problems (Auto-detected)
# ============================================================
def evaluate_quixbugs(
    mode="baseline",
    out_file=None,
    model=None,
    limit=None,
    problem=None,
    retrieval_profile=None,
    index_dir=None,
    trace_dir=None,
    use_failure_signal: bool = USE_FAILURE_SIGNAL_BY_DEFAULT,
    rag_max_attempts: int = DEFAULT_RAG_MAX_ATTEMPTS,
    rag_k: int = 2,
    rag_candidates: int = DEFAULT_RAG_CANDIDATES,
    retrieval_variant: str = "structured",
    disabled_components: frozenset[str] | None = None,
):
    if out_file is None:
        out_file = f"experiments/quixbugs_repair_{mode}.json"

    os.makedirs("experiments", exist_ok=True)

    repair_fn = repair_without_rag if mode == "baseline" else repair_with_rag

    problems = autodetect_problems()
    if problem:
        if problem not in problems:
            raise ValueError(f"Problem {problem} not found in detected QuixBugs set")
        problems = [problem]
    if limit:
        problems = problems[:limit]
    print(f"\nDetected {len(problems)} QuixBugs problems:")
    for p in problems:
        print(" -", p)

    results = load_existing_results(out_file)
    completed = {item["problem"] for item in results}

    for p in problems:
        if p in completed:
            continue
        try:
            ok = evaluate_problem(
                p,
                repair_fn,
                mode,
                model=model,
                retrieval_profile=retrieval_profile,
                index_dir=index_dir,
                trace_dir=trace_dir,
                use_failure_signal=use_failure_signal,
                rag_max_attempts=rag_max_attempts,
                rag_k=rag_k,
                rag_candidates=rag_candidates,
                retrieval_variant=retrieval_variant,
                disabled_components=disabled_components,
            )
        except InfrastructureFailure as exc:
            print(f"[ABORT] Stopping run due to infrastructure failure: {exc}")
            break
        results.append(
            {
                "problem": p,
                "pass": ok,
                "retrieval_variant": retrieval_variant if mode == "rag" else None,
                "use_failure_signal": use_failure_signal,
                "rag_k": rag_k if mode == "rag" else None,
                "rag_candidates": rag_candidates if mode == "rag" else None,
                "rag_max_attempts": rag_max_attempts if mode == "rag" else None,
            }
        )
        completed.add(p)
        save_results(out_file, results)

    total = len(results)
    passed = sum(r["pass"] for r in results)
    if total == 0:
        print(f"\n[{mode.upper()}] 0/0 = aborted before any problem completed")
    else:
        print(f"\n[{mode.upper()}] {passed}/{total} = {passed/total*100:.2f}%")
    return results


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "rag"], default="rag")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out-file", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--problem", default=None)
    parser.add_argument("--retrieval-profile", default=None)
    parser.add_argument("--retrieval-index-dir", default=None)
    parser.add_argument("--trace-dir", default=None)
    parser.add_argument("--use-failure-signal", action="store_true")
    parser.add_argument("--rag-max-attempts", type=int, default=DEFAULT_RAG_MAX_ATTEMPTS)
    parser.add_argument("--rag-k", type=int, default=2)
    parser.add_argument("--rag-candidates", type=int, default=DEFAULT_RAG_CANDIDATES)
    parser.add_argument(
        "--retrieval-variant",
        choices=["structured", "code_only", "raw_text", "raw_text_rerank"],
        default="structured",
    )
    parser.add_argument(
        "--paper-primary",
        action="store_true",
        help="Use the paper primary setting: one attempt, one candidate, failure signal enabled.",
    )
    args = parser.parse_args()

    if args.paper_primary:
        args.use_failure_signal = True
        args.rag_max_attempts = 1
        args.rag_candidates = 1

    evaluate_quixbugs(
        mode=args.mode,
        out_file=args.out_file,
        model=args.model,
        limit=args.limit,
        problem=args.problem,
        retrieval_profile=args.retrieval_profile or ("repair_clean" if args.mode == "rag" else None),
        index_dir=args.retrieval_index_dir,
        trace_dir=args.trace_dir,
        use_failure_signal=args.use_failure_signal,
        rag_max_attempts=args.rag_max_attempts,
        rag_k=args.rag_k,
        rag_candidates=args.rag_candidates,
        retrieval_variant=args.retrieval_variant,
    )
