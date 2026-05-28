from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.repair_baseline import repair_without_rag
from src.models.repair_rag import repair_with_rag
from src.retrieval.failure_state import make_failure_state


DEFAULT_INPUT = "data/humanevalfix/HumanEvalFix.jsonl"
HUMANEVALFIX_PREAMBLE = (
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


class InfrastructureFailure(Exception):
    pass


def load_tasks(path: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with open(path) as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                tasks.append(json.loads(stripped))
    return tasks


def load_existing_results(path: str) -> list[dict[str, Any]]:
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


def save_results(path: str, results: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as handle:
        json.dump(results, handle, indent=2)


def write_trace(trace_dir: str | None, mode: str, task_id: str, payload: dict[str, Any]) -> None:
    if not trace_dir:
        return
    os.makedirs(trace_dir, exist_ok=True)
    safe_id = task_id.replace("/", "_")
    path = Path(trace_dir) / f"{mode}__{safe_id}.json"
    path.write_text(json.dumps(payload, indent=2))


def code_for_prompt_mode(task: dict[str, Any], prompt_mode: str) -> tuple[str, str]:
    if prompt_mode == "docs":
        return task["buggy_code_docs"], task["fixed_code_docs"]
    return task["buggy_code_tests"], task["fixed_code_tests"]


def build_failure_signal(task: dict[str, Any], prompt_mode: str) -> str:
    sections = [
        f"Task id: {task['task_id']}",
        f"Entry point: {task['entry_point']}",
        f"Bug type: {task.get('bug_type', '')}",
        f"Failure symptoms: {task.get('failure_symptoms', '')}",
    ]
    if prompt_mode == "docs":
        doc = task.get("docstring") or task.get("instruction") or task.get("prompt") or ""
        if doc:
            sections.append(f"Specification:\n{doc}")
    sections.append(f"Tests:\n{task['test']}")
    return "\n\n".join(section for section in sections if section.strip())


def maybe_prepend_declaration(candidate: str, declaration: str, entry_point: str) -> str:
    if f"def {entry_point}" in candidate:
        return candidate
    stripped = candidate.strip("\n")
    if not stripped:
        return candidate
    if all(line.startswith((" ", "\t")) or not line.strip() for line in stripped.splitlines()):
        return declaration + stripped + "\n"
    return candidate


def run_candidate(task: dict[str, Any], candidate_code: str, timeout_seconds: int) -> tuple[bool, str, str]:
    source = (
        HUMANEVALFIX_PREAMBLE
        + "\n"
        + candidate_code
        + "\n\n"
        + task["test"]
        + "\n"
        + f"check({task['entry_point']})\n"
    )
    with tempfile.TemporaryDirectory(prefix="humanevalfix_") as temp_dir:
        candidate_path = Path(temp_dir) / "candidate.py"
        candidate_path.write_text(source)
        spec = importlib.util.spec_from_file_location("candidate", candidate_path)
        if spec is None or spec.loader is None:
            return False, "", "Unable to load candidate module spec."
        module = importlib.util.module_from_spec(spec)
        sys.modules["candidate"] = module

        def handler(signum, frame):
            raise TimeoutError(f"Timed out after {timeout_seconds} seconds")

        if hasattr(__import__("signal"), "SIGALRM"):
            import signal

            previous_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(timeout_seconds)
            try:
                spec.loader.exec_module(module)
                return True, "", ""
            except Exception:
                return False, "", traceback.format_exc()
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous_handler)

        try:
            spec.loader.exec_module(module)
            return True, "", ""
        except Exception:
            return False, "", traceback.format_exc()


def evaluate_task(
    task: dict[str, Any],
    mode: str,
    model: str | None,
    prompt_mode: str,
    retrieval_profile: str | None,
    index_dir: str | None,
    retrieval_variant: str,
    timeout_seconds: int,
    trace_dir: str | None,
) -> dict[str, Any]:
    buggy_code, fixed_code = code_for_prompt_mode(task, prompt_mode)
    failure_signal = build_failure_signal(task, prompt_mode)
    failure_state = make_failure_state(failure_signal, buggy_code).to_dict()
    repair_debug: dict[str, Any] | None = None

    if mode == "baseline":
        repaired = repair_without_rag(
            buggy_code,
            description=failure_signal,
            model=model,
            return_debug=bool(trace_dir),
        )
    else:
        repaired = repair_with_rag(
            buggy_code,
            description=failure_signal,
            model=model,
            retrieval_profile=retrieval_profile,
            index_dir=index_dir,
            retrieval_variant=retrieval_variant,
            failure_state=failure_state,
            return_debug=bool(trace_dir),
        )

    if isinstance(repaired, dict):
        repair_debug = repaired
        candidate_code = repaired["code"]
    else:
        candidate_code = repaired

    candidate_code = maybe_prepend_declaration(
        candidate_code,
        declaration=task.get("declaration") or task.get("prompt") or "",
        entry_point=task["entry_point"],
    )
    passed, stdout, stderr = run_candidate(task, candidate_code, timeout_seconds)

    result = {
        "task_id": task["task_id"],
        "entry_point": task["entry_point"],
        "mode": mode,
        "retrieval_variant": retrieval_variant if mode == "rag" else None,
        "prompt_mode": prompt_mode,
        "bug_type": task.get("bug_type"),
        "failure_symptoms": task.get("failure_symptoms"),
        "pass": passed,
        "stdout": stdout,
        "stderr": stderr,
    }

    trace_payload = {
        **result,
        "buggy_code": buggy_code,
        "fixed_code": fixed_code,
        "failure_signal": failure_signal,
        "failure_state": failure_state,
        "generated_code": candidate_code,
    }
    if repair_debug:
        trace_payload.update(
            {
                "messages": repair_debug.get("messages"),
                "prompt": repair_debug.get("prompt"),
                "retrieved_examples": repair_debug.get("retrieved_examples"),
                "retrieval_debug": repair_debug.get("retrieval_debug"),
            }
        )
    write_trace(trace_dir, mode, task["task_id"], trace_payload)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate baseline/RAG on HumanEvalFix.")
    parser.add_argument("--input-path", default=DEFAULT_INPUT)
    parser.add_argument("--mode", choices=["baseline", "rag"], default="baseline")
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--results-path", default=None)
    parser.add_argument("--trace-dir", default=None)
    parser.add_argument("--prompt-mode", choices=["tests", "docs"], default="tests")
    parser.add_argument("--retrieval-profile", default="repair_clean")
    parser.add_argument("--retrieval-index-dir", default=None)
    parser.add_argument(
        "--retrieval-variant",
        choices=["structured", "code_only", "raw_text", "raw_text_rerank"],
        default="structured",
    )
    parser.add_argument("--timeout-seconds", type=int, default=5)
    args = parser.parse_args()

    tasks = load_tasks(args.input_path)
    if args.limit:
        tasks = tasks[: args.limit]

    results_path = args.results_path or f"experiments/humanevalfix_{args.mode}.json"
    results = load_existing_results(results_path)
    completed = {row["task_id"] for row in results}

    print(f"Detected {len(tasks)} HumanEvalFix tasks.")
    for task in tasks:
        if task["task_id"] in completed:
            continue
        print(f"\n=== {task['task_id']} ({args.mode}) ===")
        try:
            row = evaluate_task(
                task=task,
                mode=args.mode,
                model=args.model,
                prompt_mode=args.prompt_mode,
                retrieval_profile=args.retrieval_profile,
                index_dir=args.retrieval_index_dir,
                retrieval_variant=args.retrieval_variant,
                timeout_seconds=args.timeout_seconds,
                trace_dir=args.trace_dir,
            )
        except Exception as exc:
            if exc.__class__.__name__ in {"APIConnectionError", "APITimeoutError"}:
                raise InfrastructureFailure(str(exc)) from exc
            row = {
                "task_id": task["task_id"],
                "entry_point": task.get("entry_point"),
                "mode": args.mode,
                "retrieval_variant": args.retrieval_variant if args.mode == "rag" else None,
                "prompt_mode": args.prompt_mode,
                "bug_type": task.get("bug_type"),
                "failure_symptoms": task.get("failure_symptoms"),
                "pass": False,
                "stdout": "",
                "stderr": f"[ERROR] {exc}\n{traceback.format_exc()}",
            }

        print("PASS" if row["pass"] else "FAIL")
        if row.get("stderr"):
            print(row["stderr"].splitlines()[-1][:240])
        results.append(row)
        completed.add(task["task_id"])
        save_results(results_path, results)

    passed = sum(1 for row in results if row.get("pass"))
    print(json.dumps({"results_path": results_path, "passed": passed, "total": len(results)}, indent=2))


if __name__ == "__main__":
    main()
