import json
import os


def compute_pass_rate(path):
    """
    Reads results file and computes total tasks, passed tasks, and pass rate.
    """
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        return None

    with open(path) as f:
        results = json.load(f)

    total = len(results)
    passed = sum(1 for r in results if r.get("pass") is True)
    rate = passed / total * 100 if total > 0 else 0

    return {
        "file": path,
        "total": total,
        "passed": passed,
        "pass_rate": rate,
    }


def main():
    baseline_path = "experiments/mbpp_baseline_results.json"
    rag_path = "experiments/mbpp_gen_results.json"

    print("\n====== COMPUTING PASS RATES ======\n")

    baseline = compute_pass_rate(baseline_path)
    rag = compute_pass_rate(rag_path)

    if not baseline or not rag:
        print("Missing result files. Run evaluations first.")
        return

    print("=== BASELINE RESULTS ===")
    print(f"Total tasks: {baseline['total']}")
    print(f"Passed: {baseline['passed']}")
    print(f"Pass rate: {baseline['pass_rate']:.2f}%\n")

    print("=== RAG RESULTS ===")
    print(f"Total tasks: {rag['total']}")
    print(f"Passed: {rag['passed']}")
    print(f"Pass rate: {rag['pass_rate']:.2f}%\n")

    diff = rag["pass_rate"] - baseline["pass_rate"]

    print("=== COMPARISON ===")
    if diff > 0:
        print(f"RAG IMPROVES accuracy by {diff:.2f}%")
    elif diff < 0:
        print(f"RAG DECREASES accuracy by {-diff:.2f}%")
    else:
        print("RAG has no effect on accuracy.")


if __name__ == "__main__":
    main()
