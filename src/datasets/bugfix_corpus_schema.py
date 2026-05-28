from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BenchmarkName = Literal["humaneval", "mbpp", "quixbugs"]


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip().lower()


@dataclass(slots=True)
class BugFixRecord:
    """Normalized bug-fix record for external retrieval corpora."""

    id: str
    source_dataset: str
    source_split: str
    language: str
    task_family: str
    repository: str
    instance_id: str
    buggy_code: str
    fixed_code: str
    file_path: str = ""
    function_name: str = ""
    prompt: str = ""
    bug_type: str = "unknown"
    failure_signal: str = ""
    tests: list[str] = field(default_factory=list)
    commit_buggy: str = ""
    commit_fixed: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_retrieval_json(self) -> dict[str, Any]:
        """Backwards-compatible JSON shape for the current index builders."""
        return {
            "id": self.id,
            "source": self.source_dataset,
            "buggy_code": self.buggy_code,
            "fixed_code": self.fixed_code,
            "bug_type": self.bug_type,
            "prompt": self.prompt,
            "tests": self.tests,
            "source_split": self.source_split,
            "language": self.language,
            "task_family": self.task_family,
            "repository": self.repository,
            "instance_id": self.instance_id,
            "file_path": self.file_path,
            "function_name": self.function_name,
            "failure_signal": self.failure_signal,
            "commit_buggy": self.commit_buggy,
            "commit_fixed": self.commit_fixed,
            "metadata": self.metadata,
        }


def validate_record(record: BugFixRecord) -> list[str]:
    issues: list[str] = []

    if not record.id.strip():
        issues.append("missing id")
    if not record.source_dataset.strip():
        issues.append("missing source_dataset")
    if record.language.lower() != "python":
        issues.append("language must be python")
    if not record.buggy_code.strip():
        issues.append("missing buggy_code")
    if not record.fixed_code.strip():
        issues.append("missing fixed_code")
    if _normalize_text(record.buggy_code) == _normalize_text(record.fixed_code):
        issues.append("buggy_code and fixed_code are identical")
    if record.source_dataset in {"mbpp", "mbpp_synthetic", "quixbugs", "humaneval"}:
        issues.append("evaluation-derived source_dataset should not be used in external corpus")

    return issues


def should_include_record(
    record: BugFixRecord,
    target_benchmark: BenchmarkName | None = None,
) -> tuple[bool, str]:
    """
    Filtering rules for a defensible external bug-fix corpus.

    Returns (include, reason).
    """
    issues = validate_record(record)
    if issues:
        return False, "; ".join(issues)

    if record.metadata.get("synthetic") is True:
        return False, "synthetic record"

    if record.metadata.get("generated") is True:
        return False, "generated record"

    if record.metadata.get("has_repro") is False:
        return False, "missing reproducible failure signal"

    if record.metadata.get("files_changed", 1) > 3:
        return False, "too many files changed"

    if record.metadata.get("changed_lines", 0) > 80:
        return False, "patch too large"

    if record.metadata.get("non_code_fix_only") is True:
        return False, "non-code-only fix"

    if record.metadata.get("framework_heavy") is True:
        return False, "framework-heavy fix"

    if record.metadata.get("scope") not in {"function", "method", "small_module"}:
        return False, "scope too broad"

    if target_benchmark == "humaneval":
        if record.task_family not in {"algorithmic_python", "general_python"}:
            return False, "task family not aligned with Humaneval generation"

    if target_benchmark == "mbpp":
        if record.source_dataset in {"mbpp", "mbpp_synthetic"}:
            return False, "MBPP overlap"
        if record.instance_id.startswith("mbpp_"):
            return False, "MBPP-derived instance"

    if target_benchmark == "quixbugs":
        if record.source_dataset == "quixbugs":
            return False, "QuixBugs overlap"
        if record.instance_id.startswith("quixbugs_"):
            return False, "QuixBugs-derived instance"

    return True, "ok"


def recommended_source_priority() -> list[dict[str, str]]:
    """
    Ranked sources for this project.
    """
    return [
        {
            "name": "BugsInPy",
            "role": "primary",
            "why": "real Python bugs with reproducible buggy and fixed versions",
        },
        {
            "name": "PyBugHive",
            "role": "primary",
            "why": "curated Python bug benchmark with reproducibility metadata",
        },
        {
            "name": "BugSwarm (Python-only filtered subset)",
            "role": "secondary",
            "why": "adds scale if you aggressively filter out CI/config noise",
        },
        {
            "name": "FixEval",
            "role": "optional",
            "why": "useful as an algorithmic-style auxiliary corpus, not a replacement for real repo bugs",
        },
    ]
