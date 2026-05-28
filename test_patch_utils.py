import json

from src.models.patch_utils import (
    apply_line_range_response,
    extract_referenced_lines,
    parse_line_range_edits,
    select_patch_snippets,
)


def response_for(edits):
    return json.dumps({"edits": edits})


def test_applies_single_line_replacement():
    source = "a = 1\nb = 2\nc = 3\n"
    result = apply_line_range_response(
        source,
        response_for(
            [
                {
                    "start_line": 2,
                    "end_line": 2,
                    "original": "b = 2\n",
                    "replacement": "b = 4\n",
                }
            ]
        ),
    )

    assert result.status == "applied"
    assert result.code == "a = 1\nb = 4\nc = 3\n"
    assert result.applied_edits == [
        {"original_index": 0, "start_line": 2, "end_line": 2, "status": "applied"}
    ]


def test_applies_multi_line_replacement():
    source = "def f():\n    x = 1\n    y = 2\n    return x\n"
    result = apply_line_range_response(
        source,
        response_for(
            [
                {
                    "start_line": 2,
                    "end_line": 4,
                    "original": "    x = 1\n    y = 2\n    return x\n",
                    "replacement": "    x = 1\n    y = 2\n    return x + y\n",
                }
            ]
        ),
    )

    assert result.status == "applied"
    assert result.code == "def f():\n    x = 1\n    y = 2\n    return x + y\n"


def test_applies_multiple_edits_bottom_up_to_avoid_line_shift():
    source = "a\nb\nc\nd\n"
    result = apply_line_range_response(
        source,
        response_for(
            [
                {
                    "start_line": 1,
                    "end_line": 2,
                    "original": "a\nb\n",
                    "replacement": "A\n",
                },
                {
                    "start_line": 4,
                    "end_line": 4,
                    "original": "d\n",
                    "replacement": "D\n",
                },
            ]
        ),
    )

    assert result.status == "applied"
    assert result.code == "A\nc\nD\n"


def test_rejects_invalid_insertion_range():
    source = "a\nb\n"
    result = apply_line_range_response(
        source,
        response_for(
            [
                {
                    "start_line": 3,
                    "end_line": 2,
                    "original": "",
                    "replacement": "c\n",
                }
            ]
        ),
    )

    assert result.status == "rejected"
    assert result.code == source
    assert "invalid line range" in result.rejection_reason


def test_rejects_original_text_mismatch():
    source = "a\nb\n"
    result = apply_line_range_response(
        source,
        response_for(
            [
                {
                    "start_line": 2,
                    "end_line": 2,
                    "original": "wrong\n",
                    "replacement": "B\n",
                }
            ]
        ),
    )

    assert result.status == "rejected"
    assert result.code == source
    assert result.edits == [
        {
            "start_line": 2,
            "end_line": 2,
            "original": "wrong\n",
            "replacement": "B\n",
        }
    ]
    assert "original text mismatch" in result.rejection_reason


def test_matches_original_after_line_ending_normalization_only():
    source = "a\r\nb\r\n"
    result = apply_line_range_response(
        source,
        response_for(
            [
                {
                    "start_line": 2,
                    "end_line": 2,
                    "original": "b\n",
                    "replacement": "B\r\n",
                }
            ]
        ),
    )

    assert result.status == "applied"
    assert result.code == "a\r\nB\r\n"


def test_accepts_missing_terminal_newline_in_original_and_restores_replacement_newline():
    source = "a\nb\nc\n"
    result = apply_line_range_response(
        source,
        response_for(
            [
                {
                    "start_line": 2,
                    "end_line": 2,
                    "original": "b",
                    "replacement": "B",
                }
            ]
        ),
    )

    assert result.status == "applied"
    assert result.code == "a\nB\nc\n"


def test_parses_required_line_range_schema_only():
    edits = parse_line_range_edits(
        response_for(
            [
                {
                    "start_line": "1",
                    "end_line": "1",
                    "original": "a\n",
                    "replacement": "A\n",
                }
            ]
        )
    )

    assert edits == [
        {
            "start_line": 1,
            "end_line": 1,
            "original": "a\n",
            "replacement": "A\n",
        }
    ]


def test_extracts_referenced_lines_from_traceback_and_pytest_locations():
    description = """
    File "src/black/__init__.py", line 123, in format_file
    tests/test_black.py:456: AssertionError
    """

    assert extract_referenced_lines(description) == [123, 456]


def test_select_patch_snippets_prioritizes_referenced_line_window():
    source = "\n".join(f"line_{i} = {i}" for i in range(1, 220))
    snippets = select_patch_snippets(
        source,
        'File "src/black/__init__.py", line 150, in target',
        max_snippets=2,
        window_lines=80,
        window_stride=80,
        focused_window_lines=20,
    )

    assert snippets[0]["source"] == "referenced_line"
    assert snippets[0]["start_line"] <= 150 <= snippets[0]["end_line"]
