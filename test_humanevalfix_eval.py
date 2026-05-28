from src.datasets.import_humanevalfix import normalize_row
from src.eval.evaluate_humanevalfix import build_failure_signal, run_candidate


def sample_raw_row():
    return {
        "task_id": "Python/0",
        "declaration": "def add_one(x):\n",
        "prompt": "def add_one(x):\n    \"\"\"Return x plus one.\"\"\"\n",
        "canonical_solution": "    return x + 1\n",
        "buggy_solution": "    return x - 1\n",
        "test": "def check(fn):\n    assert fn(1) == 2\n",
        "entry_point": "add_one",
        "bug_type": "operator",
        "failure_symptoms": "wrong arithmetic",
    }


def test_normalize_row_builds_tests_and_docs_code():
    row = normalize_row(sample_raw_row(), source_url="local")

    assert row["buggy_code_tests"] == "def add_one(x):\n    return x - 1\n"
    assert "\"\"\"Return x plus one.\"\"\"" in row["buggy_code_docs"]
    assert row["source_task"] == "humanevalfix-python"


def test_build_failure_signal_includes_tests():
    row = normalize_row(sample_raw_row(), source_url="local")

    signal = build_failure_signal(row, prompt_mode="tests")

    assert "Bug type: operator" in signal
    assert "def check(fn):" in signal


def test_run_candidate_passes_and_fails():
    row = normalize_row(sample_raw_row(), source_url="local")

    ok, _, err = run_candidate(row, row["fixed_code_tests"], timeout_seconds=2)
    bad, _, bad_err = run_candidate(row, row["buggy_code_tests"], timeout_seconds=2)

    assert ok, err
    assert not bad
    assert "AssertionError" in bad_err
