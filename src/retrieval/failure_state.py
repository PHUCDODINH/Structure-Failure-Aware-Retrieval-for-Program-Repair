from __future__ import annotations

import re
from dataclasses import asdict, dataclass


IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ERROR_NAME_RE = re.compile(r"\b([A-Z][A-Za-z]+(?:Error|Exception|Warning))\b")
PYTEST_NODE_RE = re.compile(r"([\w./-]+\.py(?:::[A-Za-z_][A-Za-z0-9_]*)+)")
DEF_TEST_RE = re.compile(r"\bdef\s+(test_[A-Za-z0-9_]+)\s*\(")

STOPWORDS = {
    "assert",
    "assertionerror",
    "class",
    "def",
    "error",
    "expected",
    "failed",
    "false",
    "file",
    "from",
    "import",
    "none",
    "observed",
    "optional",
    "passed",
    "pytest",
    "return",
    "self",
    "test",
    "tests",
    "traceback",
    "true",
    "with",
}

CONTRACT_TAG_RULES = {
    "ordering": ("order", "ordered", "sort", "sorted", "topological", "queue", "heap", "priority"),
    "edge_case": ("empty", "none", "null", "default", "zero", "negative", "boundary", "edge"),
    "whitespace": ("space", "whitespace", "indent", "dedent", "strip", "lstrip", "rstrip", "wrap"),
    "type_mismatch": ("typeerror", "attributeerror", "object", "list", "tuple", "dict", "set"),
    "graph_dependency": ("graph", "node", "edge", "incoming", "outgoing", "successor", "predecessor"),
    "collection_update": ("append", "pop", "insert", "remove", "extend", "list", "dict", "set"),
    "boundary": ("index", "range", "start", "end", "length", "len", "off-by-one", "boundary"),
    "recursion": ("recursive", "recursion", "base case", "yield from"),
    "arithmetic": ("sum", "max", "min", "count", "total", "accumulator", "divide", "multiply"),
    "api_usage": ("api", "argument", "parameter", "call", "method", "attribute", "keyword"),
}


@dataclass(frozen=True)
class FailureState:
    raw_failure_text: str
    failure_mode: str
    exception_type: str
    test_name: str
    assertion_summary: str
    suspicious_symbols: list[str]
    contract_tags: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def make_failure_state(raw_failure_text: str, buggy_code: str = "") -> FailureState:
    raw = raw_failure_text or ""
    combined = f"{raw}\n{buggy_code}"
    failure_mode = infer_failure_mode(raw)
    exception_type = infer_exception_type(raw)
    test_name = infer_test_name(raw)
    assertion_summary = infer_assertion_summary(raw)
    suspicious_symbols = extract_suspicious_symbols(combined)
    contract_tags = infer_contract_tags(combined, failure_mode, exception_type)
    return FailureState(
        raw_failure_text=raw,
        failure_mode=failure_mode,
        exception_type=exception_type,
        test_name=test_name,
        assertion_summary=assertion_summary,
        suspicious_symbols=suspicious_symbols,
        contract_tags=contract_tags,
    )


def infer_failure_mode(text: str) -> str:
    lowered = text.lower()
    if "timeout" in lowered or "exceeded" in lowered:
        return "timeout"
    if "syntaxerror" in lowered or "indentationerror" in lowered:
        return "syntax"
    if "assert" in lowered or "expected" in lowered or "!=" in text or "==" in text:
        return "assertion"
    if any(token in lowered for token in ("whitespace", "wrap", "indent", "dedent", "format")):
        return "formatting"
    if ERROR_NAME_RE.search(text) or "traceback" in lowered:
        return "runtime"
    return "semantic"


def infer_exception_type(text: str) -> str:
    match = ERROR_NAME_RE.search(text)
    if match:
        return match.group(1)
    if "AssertionError" in text or "assert " in text:
        return "AssertionError"
    return ""


def infer_test_name(text: str) -> str:
    failed_matches = re.findall(r"FAILED\s+([^\s]+)", text)
    if failed_matches:
        return failed_matches[0]
    node_match = PYTEST_NODE_RE.search(text)
    if node_match:
        return node_match.group(1)
    def_match = DEF_TEST_RE.search(text)
    if def_match:
        return def_match.group(1)
    file_match = re.search(r"Failing test file:\s*([^\s]+)", text)
    if file_match:
        return file_match.group(1)
    return ""


def infer_assertion_summary(text: str, max_chars: int = 300) -> str:
    interesting_prefixes = ("E       ", ">       ", "assert ", "AssertionError")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(interesting_prefixes) or "AssertionError" in stripped:
            lines.append(stripped)
        elif "assert " in stripped and len(stripped) < 220:
            lines.append(stripped)
        if len(" ".join(lines)) >= max_chars:
            break
    summary = " ".join(lines)
    return summary[:max_chars].strip()


def extract_suspicious_symbols(text: str, limit: int = 24) -> list[str]:
    seen: list[str] = []
    for token in IDENTIFIER_RE.findall(text):
        lowered = token.lower()
        if len(token) < 3 or lowered in STOPWORDS:
            continue
        if token not in seen:
            seen.append(token)
        if len(seen) >= limit:
            break
    return seen


def infer_contract_tags(text: str, failure_mode: str = "", exception_type: str = "") -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, markers in CONTRACT_TAG_RULES.items():
        if any(marker in lowered for marker in markers):
            tags.append(tag)
    if failure_mode == "timeout" and "recursion" not in tags:
        tags.append("recursion")
    if failure_mode == "formatting" and "whitespace" not in tags:
        tags.append("whitespace")
    if exception_type in {"TypeError", "AttributeError"} and "type_mismatch" not in tags:
        tags.append("type_mismatch")
    return tags
