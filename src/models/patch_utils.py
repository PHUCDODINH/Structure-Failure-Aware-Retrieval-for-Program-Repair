import json
import re
from dataclasses import dataclass


PATCH_SCHEMA_VERSION = "line_range_v1"
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FILE_LINE_RE = re.compile(r"(?:File\s+)?[\"']?([^\"'\s:]+\.py)[\"']?,?\s+line\s+(\d+)|([^\s:]+\.py):(\d+)")


class PatchApplicationError(ValueError):
    pass


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def extract_json_object(text: str) -> str:
    stripped = strip_code_fences(text)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return stripped
    return stripped[start:end + 1]


def coerce_positive_int(value) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def parse_line_range_edits(text: str) -> list[dict]:
    payload = json.loads(extract_json_object(text))
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise PatchApplicationError("missing edits")

    normalized: list[dict] = []
    for item in edits:
        if not isinstance(item, dict):
            continue
        start_line = coerce_positive_int(item.get("start_line"))
        end_line = coerce_positive_int(item.get("end_line"))
        original = item.get("original")
        replacement = item.get("replacement")
        if start_line is None or end_line is None:
            continue
        if not isinstance(original, str) or not isinstance(replacement, str):
            continue
        normalized.append(
            {
                "start_line": start_line,
                "end_line": end_line,
                "original": original,
                "replacement": replacement,
            }
        )

    if not normalized:
        raise PatchApplicationError("no valid line-range edits")
    return normalized


def parse_legacy_search_replace_edits(text: str) -> list[dict]:
    payload = json.loads(extract_json_object(text))
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise PatchApplicationError("missing edits")

    normalized: list[dict] = []
    for item in edits:
        if not isinstance(item, dict):
            continue
        search = item.get("search")
        replace = item.get("replace")
        if isinstance(search, str) and isinstance(replace, str) and search:
            normalized_edit = {"search": search, "replace": replace}
            for key in ("start_line", "end_line"):
                value = coerce_positive_int(item.get(key))
                if value is not None:
                    normalized_edit[key] = value
            normalized.append(normalized_edit)

    if not normalized:
        raise PatchApplicationError("no valid legacy edits")
    return normalized


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def terminal_line_ending(text: str) -> str:
    if text.endswith("\r\n"):
        return "\r\n"
    if text.endswith("\n"):
        return "\n"
    if text.endswith("\r"):
        return "\r"
    return ""


def remove_one_terminal_line_ending(text: str) -> str:
    ending = terminal_line_ending(text)
    if not ending:
        return text
    return text[: -len(ending)]


def original_matches_source_span(source_span: str, expected: str) -> bool:
    if normalize_line_endings(source_span) == normalize_line_endings(expected):
        return True
    if terminal_line_ending(source_span) and not terminal_line_ending(expected):
        return normalize_line_endings(remove_one_terminal_line_ending(source_span)) == normalize_line_endings(expected)
    return False


def normalize_replacement_for_span(source_span: str, replacement: str) -> str:
    ending = terminal_line_ending(source_span)
    if not ending or not replacement or terminal_line_ending(replacement):
        return replacement
    return replacement + ending


def line_offsets(source_text: str) -> list[int]:
    offsets: list[int] = []
    offset = 0
    for line in source_text.splitlines(keepends=True):
        offsets.append(offset)
        offset += len(line)
    offsets.append(offset)
    return offsets


def source_span_for_lines(source_text: str, start_line: int, end_line: int) -> tuple[int, int, str]:
    source_lines = source_text.splitlines(keepends=True)
    if start_line < 1 or end_line < start_line:
        raise PatchApplicationError(f"invalid line range {start_line}-{end_line}")
    if end_line > len(source_lines):
        raise PatchApplicationError(
            f"line range {start_line}-{end_line} exceeds file length {len(source_lines)}"
        )

    offsets = line_offsets(source_text)
    start_offset = offsets[start_line - 1]
    end_offset = offsets[end_line]
    return start_offset, end_offset, source_text[start_offset:end_offset]


def apply_line_range_edits(source_text: str, edits: list[dict]) -> tuple[str, list[dict]]:
    updated = source_text
    applied: list[dict] = []

    sorted_edits = sorted(
        enumerate(edits),
        key=lambda item: (item[1]["start_line"], item[1]["end_line"], item[0]),
        reverse=True,
    )
    occupied_ranges: list[tuple[int, int]] = []

    for original_index, edit in sorted_edits:
        start_line = edit["start_line"]
        end_line = edit["end_line"]
        if any(not (end_line < used_start or start_line > used_end) for used_start, used_end in occupied_ranges):
            raise PatchApplicationError(f"overlapping edit range {start_line}-{end_line}")

        start_offset, end_offset, source_span = source_span_for_lines(updated, start_line, end_line)
        expected = edit["original"]
        if not original_matches_source_span(source_span, expected):
            raise PatchApplicationError(
                f"original text mismatch at lines {start_line}-{end_line}"
            )

        replacement = normalize_replacement_for_span(source_span, edit["replacement"])
        updated = updated[:start_offset] + replacement + updated[end_offset:]
        occupied_ranges.append((start_line, end_line))
        applied.append(
            {
                "original_index": original_index,
                "start_line": start_line,
                "end_line": end_line,
                "status": "applied",
            }
        )

    applied.sort(key=lambda item: item["original_index"])
    return updated, applied


@dataclass(frozen=True)
class PatchApplicationResult:
    code: str
    raw_response: str
    edits: list[dict]
    schema_version: str = PATCH_SCHEMA_VERSION
    status: str = "applied"
    applied_edits: list[dict] | None = None
    rejection_reason: str | None = None

    def to_debug_dict(self) -> dict:
        return {
            "patch_schema_version": self.schema_version,
            "patch_raw_response": self.raw_response,
            "patch_edits": self.edits,
            "patch_apply_status": self.status,
            "patch_applied_edits": self.applied_edits or [],
            "patch_rejection_reason": self.rejection_reason,
        }


def apply_line_range_response(source_text: str, raw_response: str) -> PatchApplicationResult:
    edits: list[dict] = []
    try:
        edits = parse_line_range_edits(raw_response)
        code, applied_edits = apply_line_range_edits(source_text, edits)
        return PatchApplicationResult(
            code=code,
            raw_response=raw_response,
            edits=edits,
            applied_edits=applied_edits,
        )
    except Exception as exc:
        if isinstance(exc, PatchApplicationError):
            reason = str(exc)
        else:
            reason = f"{exc.__class__.__name__}: {exc}"
        return PatchApplicationResult(
            code=source_text,
            raw_response=raw_response,
            edits=edits,
            status="rejected",
            applied_edits=[],
            rejection_reason=reason,
        )


def format_numbered_snippet(snippet: dict) -> str:
    start_line = int(snippet["start_line"])
    lines = snippet.get("text", "").splitlines()
    numbered = [f"{start_line + offset:>5}: {line}" for offset, line in enumerate(lines)]
    return (
        f"Snippet lines {snippet['start_line']}-{snippet['end_line']} "
        "(line numbers are not part of the file):\n"
        + "\n".join(numbered)
    )


def extract_query_terms(description: str) -> list[str]:
    seen: list[str] = []
    stopwords = {
        "traceback",
        "assertionerror",
        "optional",
        "description",
        "failed",
        "error",
        "observed",
        "signal",
        "running",
        "warning",
        "requirements",
        "install",
    }
    for token in IDENTIFIER_RE.findall(description.lower()):
        if len(token) < 4:
            continue
        if token in stopwords:
            continue
        if token not in seen:
            seen.append(token)
    return seen[:32]


def extract_referenced_lines(description: str) -> list[int]:
    seen: list[int] = []
    for match in FILE_LINE_RE.finditer(description):
        line_text = match.group(2) or match.group(4)
        if not line_text:
            continue
        line_no = int(line_text)
        if line_no > 0 and line_no not in seen:
            seen.append(line_no)
    return seen[:12]


def build_patch_snippet(
    lines: list[str],
    start: int,
    end: int,
    score: float,
    source: str,
) -> dict:
    return {
        "start_line": start + 1,
        "end_line": end,
        "text": "\n".join(lines[start:end]),
        "score": round(score, 4),
        "source": source,
    }


def select_patch_snippets(
    buggy_code: str,
    description: str,
    *,
    max_snippets: int = 4,
    window_lines: int = 160,
    window_stride: int = 100,
    focused_window_lines: int = 60,
) -> list[dict]:
    lines = buggy_code.splitlines()
    if not lines:
        return []

    query_terms = extract_query_terms(description)
    referenced_lines = extract_referenced_lines(description)
    candidates: list[dict] = []

    for line_no in referenced_lines:
        center = line_no - 1
        start = max(0, center - focused_window_lines // 2)
        end = min(len(lines), start + focused_window_lines)
        start = max(0, end - focused_window_lines)
        candidates.append(build_patch_snippet(lines, start, end, 100.0, "referenced_line"))

    lowered_description = description.lower()
    for start in range(0, len(lines), window_stride):
        end = min(len(lines), start + window_lines)
        if start >= end:
            continue
        snippet_text = "\n".join(lines[start:end]).lower()
        score = 0.0
        for term in query_terms:
            if term in snippet_text:
                score += 1.0
        if any(term in lowered_description for term in ("docstring", "comment", "whitespace", "format")):
            score += snippet_text.count("comment")
            score += snippet_text.count("docstring")
        candidates.append(build_patch_snippet(lines, start, end, score, "term_window"))
        if end == len(lines):
            break

    candidates.sort(key=lambda item: (item["score"], -(item["end_line"] - item["start_line"])), reverse=True)

    selected: list[dict] = []
    used_ranges: list[tuple[int, int]] = []
    for candidate in candidates:
        start = candidate["start_line"] - 1
        end = candidate["end_line"]
        if any(not (end <= used_start or start >= used_end) for used_start, used_end in used_ranges):
            continue
        selected.append(candidate)
        used_ranges.append((start, end))
        if len(selected) >= max_snippets:
            break

    if not selected:
        selected.append(
            build_patch_snippet(
                lines,
                0,
                min(len(lines), window_lines),
                0.0,
                "fallback_start",
            )
        )
    return selected
