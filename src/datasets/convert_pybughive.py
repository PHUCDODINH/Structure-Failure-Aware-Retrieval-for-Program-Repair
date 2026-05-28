from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.datasets.bugfix_corpus_schema import BugFixRecord


def run_git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def ensure_repo(repo_cache_root: Path, username: str, repository: str) -> Path | None:
    repo_dir = repo_cache_root / repository
    github_url = f"https://github.com/{username}/{repository}"
    if repo_dir.exists():
        fetch = run_git(repo_dir, "fetch", "--all", "--tags")
        if fetch.returncode != 0:
            print(f"[WARN] git fetch failed for {repository}: {fetch.stderr.strip()}")
        return repo_dir

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    clone = subprocess.run(
        ["git", "clone", github_url, str(repo_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if clone.returncode != 0:
        print(f"[WARN] git clone failed for {repository}: {clone.stderr.strip()}")
        return None
    return repo_dir


def load_file_at_commit(repo_dir: Path, commit: str, file_path: str) -> str | None:
    shown = run_git(repo_dir, "show", f"{commit}:{file_path}")
    if shown.returncode != 0:
        return None
    return shown.stdout


def count_patch_lines(patch_text: str) -> int:
    count = 0
    for line in patch_text.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def infer_scope(changed_files: int, changed_lines: int) -> str:
    if changed_files == 1 and changed_lines <= 40:
        return "function"
    if changed_files <= 2 and changed_lines <= 80:
        return "method"
    return "small_module"


def looks_like_test_file(file_path: str) -> bool:
    lowered = file_path.lower()
    name = Path(file_path).name.lower()
    if "/test" in lowered or "/tests/" in lowered:
        return True
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    return False


def source_python_files(issue: dict) -> list[dict]:
    commit = issue["commits"][0]
    return [
        item
        for item in commit["stat"]["files"]
        if item["filename"].endswith(".py") and not looks_like_test_file(item["filename"])
    ]


def normalize_issue(
    username: str,
    repository: str,
    issue: dict,
    repo_dir: Path,
) -> list[BugFixRecord]:
    commit = issue["commits"][0]
    buggy_commit = commit["parents"]
    fixed_commit = commit["hash"]
    test_files = [item["filename"] for item in commit["stat"].get("tests", [])]
    failure_signal = issue.get("testSteps", "") or issue.get("testStepsFull", "")
    project_files = source_python_files(issue)
    changed_lines = sum(count_patch_lines(item.get("patch", "")) for item in project_files)
    scope = infer_scope(len(project_files), changed_lines)

    records: list[BugFixRecord] = []
    for file_item in project_files:
        file_path = file_item["filename"]
        buggy_code = load_file_at_commit(repo_dir, buggy_commit, file_path)
        fixed_code = load_file_at_commit(repo_dir, fixed_commit, file_path)
        if not buggy_code or not fixed_code or buggy_code == fixed_code:
            continue

        relative_name = file_path.replace("/", ":")
        records.append(
            BugFixRecord(
                id=f"pybughive:{repository}:{issue['id']}:{relative_name}",
                source_dataset="pybughive",
                source_split="train",
                language="python",
                task_family="general_python",
                repository=f"{username}/{repository}",
                instance_id=f"pybughive_{repository}_{issue['id']}",
                buggy_code=buggy_code,
                fixed_code=fixed_code,
                file_path=file_path,
                function_name="",
                prompt=issue.get("title", ""),
                bug_type=issue.get("labels", "unknown"),
                failure_signal=failure_signal,
                tests=[failure_signal] if failure_signal else [],
                commit_buggy=buggy_commit,
                commit_fixed=fixed_commit,
                metadata={
                    "scope": scope,
                    "files_changed": len(project_files),
                    "changed_lines": changed_lines,
                    "has_repro": bool(failure_signal),
                    "synthetic": False,
                    "generated": False,
                    "framework_heavy": False,
                    "non_code_fix_only": False,
                    "source_test_file": "; ".join(test_files),
                    "manually_checked": bool(issue.get("manuallyChecked")),
                },
            )
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-json",
        default="data/external_sources/PyBugHive/dataset/pybughive_current.json",
    )
    parser.add_argument("--repo-cache-root", default="data/external_sources/repo_cache")
    parser.add_argument("--output-path", default="data/external_sources/pybughive_normalized.jsonl")
    parser.add_argument("--projects", nargs="+", default=None)
    parser.add_argument("--limit-issues", type=int, default=None)
    args = parser.parse_args()

    dataset = json.loads(Path(args.dataset_json).read_text())
    repo_cache_root = Path(args.repo_cache_root)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output_path.open("w") as handle:
        for project in dataset:
            repository = project["repository"]
            if args.projects and repository not in set(args.projects):
                continue
            repo_dir = ensure_repo(repo_cache_root, project["username"], repository)
            if repo_dir is None:
                continue

            issues = project["issues"]
            if args.limit_issues:
                issues = issues[: args.limit_issues]

            for issue in issues:
                for record in normalize_issue(project["username"], repository, issue, repo_dir):
                    handle.write(json.dumps(asdict(record)) + "\n")
                    written += 1

    print(json.dumps({"output_path": str(output_path), "records_written": written}, indent=2))


if __name__ == "__main__":
    main()
