from __future__ import annotations

import difflib
import re

from src.retrieval.failure_state import CONTRACT_TAG_RULES, extract_suspicious_symbols, infer_contract_tags


OPERATOR_RE = re.compile(r"(==|!=|<=|>=|//|\*\*|[-+*/%<>])")


def infer_repair_metadata(example: dict) -> dict:
    buggy = example.get("buggy_code", "")
    fixed = example.get("fixed_code", example.get("correct_code", ""))
    file_path = example.get("file_path", "")
    changed_buggy, changed_fixed = changed_regions(buggy, fixed)
    changed_text = f"{changed_buggy}\n{changed_fixed}"
    metadata = example.get("metadata") or {}
    changed_lines = int(metadata.get("changed_lines", 0) or count_changed_lines(buggy, fixed))
    return {
        "repair_pattern_tags": infer_contract_tags(changed_text),
        "suspicious_symbols": extract_suspicious_symbols(changed_text),
        "changed_operators": sorted(OPERATOR_RE.findall(changed_text)),
        "edit_scope": infer_edit_scope(changed_text),
        "file_family": infer_file_family(file_path=file_path, text=f"{buggy}\n{fixed}"),
        "changed_lines": changed_lines,
    }


def changed_regions(buggy: str, fixed: str) -> tuple[str, str]:
    buggy_lines = buggy.splitlines()
    fixed_lines = fixed.splitlines()
    matcher = difflib.SequenceMatcher(a=buggy_lines, b=fixed_lines)
    buggy_chunks: list[str] = []
    fixed_chunks: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        buggy_chunks.extend(buggy_lines[i1:i2])
        fixed_chunks.extend(fixed_lines[j1:j2])
    return "\n".join(buggy_chunks), "\n".join(fixed_chunks)


def count_changed_lines(buggy: str, fixed: str) -> int:
    buggy_changed, fixed_changed = changed_regions(buggy, fixed)
    return len(buggy_changed.splitlines()) + len(fixed_changed.splitlines())


def infer_edit_scope(changed_text: str) -> str:
    lowered = changed_text.lower()
    if "return " in lowered:
        return "return"
    if re.search(r"\b(if|elif|while)\b", lowered):
        return "condition"
    if re.search(r"\b(for|while)\b", lowered):
        return "loop"
    if re.search(r"\.[a-zA-Z_][a-zA-Z0-9_]*\(", changed_text):
        return "api_call"
    if any(token in lowered for token in (".append", ".pop", ".insert", ".remove", ".extend", "[", "]")):
        return "data_structure_update"
    return "expression"


def infer_file_family(file_path: str = "", text: str = "") -> str:
    combined = f"{file_path}\n{text}".lower()
    if any(token in combined for token in ("black", "format", "formatter", "wrap", "whitespace", "indent")):
        return "formatter"
    if any(token in combined for token in ("graph", "node", "edge", "topological", "successor", "predecessor")):
        return "graph"
    if any(token in combined for token in ("argparse", "click", "cli", "command line", "subprocess")):
        return "cli"
    if any(token in combined for token in ("pandas", "numpy", "csv", "json", "dataframe")):
        return "data_processing"
    if any(token in combined for token in ("list", "dict", "set", "append", "pop", "collection")):
        return "collection"
    if any(token in combined for token in ("sort", "search", "recursive", "recursion", "heap", "queue")):
        return "algorithmic"
    return "general_python"


def metadata_overlap(left: list[str] | set[str], right: list[str] | set[str]) -> float:
    left_set = set(left or [])
    right_set = set(right or [])
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def compatible_failure_mode(failure_mode: str, candidate_metadata: dict) -> float:
    tags = set(candidate_metadata.get("repair_pattern_tags") or [])
    edit_scope = candidate_metadata.get("edit_scope", "")
    if failure_mode == "timeout":
        return 1.0 if "recursion" in tags or edit_scope in {"condition", "loop"} else 0.0
    if failure_mode == "formatting":
        return 1.0 if "whitespace" in tags or candidate_metadata.get("file_family") == "formatter" else 0.0
    if failure_mode == "assertion":
        return 1.0 if tags or edit_scope in {"return", "condition", "expression"} else 0.0
    if failure_mode == "runtime":
        return 1.0 if tags & {"type_mismatch", "api_usage", "collection_update", "boundary"} else 0.0
    if failure_mode == "syntax":
        return 1.0 if edit_scope in {"expression", "condition"} else 0.0
    return 0.5 if tags else 0.0


def compatible_exception(exception_type: str, candidate_metadata: dict) -> float:
    if not exception_type:
        return 0.0
    tags = set(candidate_metadata.get("repair_pattern_tags") or [])
    edit_scope = candidate_metadata.get("edit_scope", "")
    if exception_type == "AssertionError":
        return 1.0 if edit_scope in {"return", "condition", "expression"} else 0.0
    if exception_type == "TypeError":
        return 1.0 if "type_mismatch" in tags or edit_scope == "api_call" else 0.0
    if exception_type == "AttributeError":
        return 1.0 if "api_usage" in tags or "type_mismatch" in tags else 0.0
    if exception_type == "IndexError":
        return 1.0 if "boundary" in tags or "collection_update" in tags else 0.0
    if exception_type == "KeyError":
        return 1.0 if "collection_update" in tags else 0.0
    return 0.5 if tags else 0.0
