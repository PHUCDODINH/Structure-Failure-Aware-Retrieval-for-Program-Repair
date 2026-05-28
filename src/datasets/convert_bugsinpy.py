from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.datasets.bugfix_corpus_schema import BugFixRecord


def parse_shell_kv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def run_git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def ensure_repo(repo_cache_root: Path, project_name: str, github_url: str) -> Path | None:
    repo_dir = repo_cache_root / project_name
    if repo_dir.exists():
        fetch = run_git(repo_dir, "fetch", "--all", "--tags")
        if fetch.returncode != 0:
            print(f"[WARN] git fetch failed for {project_name}: {fetch.stderr.strip()}")
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
        print(f"[WARN] git clone failed for {project_name}: {clone.stderr.strip()}")
        return None
    return repo_dir


def extract_changed_python_files(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            file_path = line[len("+++ b/"):].strip()
            if file_path.endswith(".py"):
                files.append(file_path)
    return sorted(set(files))


def count_changed_lines(patch_text: str) -> int:
    count = 0
    for line in patch_text.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def load_file_at_commit(repo_dir: Path, commit: str, file_path: str) -> str | None:
    shown = run_git(repo_dir, "show", f"{commit}:{file_path}")
    if shown.returncode != 0:
        return None
    return shown.stdout


def read_test_commands(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def infer_scope(changed_files: int, changed_lines: int) -> str:
    if changed_files == 1 and changed_lines <= 40:
        return "function"
    if changed_files <= 2 and changed_lines <= 80:
        return "method"
    return "small_module"


def build_records_for_bug(
    project_name: str,
    project_dir: Path,
    bug_dir: Path,
    repo_dir: Path,
) -> list[BugFixRecord]:
    project_info = parse_shell_kv(project_dir / "project.info")
    bug_info = parse_shell_kv(bug_dir / "bug.info")
    patch_text = (bug_dir / "bug_patch.txt").read_text()

    buggy_commit = bug_info["buggy_commit_id"]
    fixed_commit = bug_info["fixed_commit_id"]
    changed_files = extract_changed_python_files(patch_text)
    changed_lines = count_changed_lines(patch_text)
    tests = read_test_commands(bug_dir / "run_test.sh")
    scope = infer_scope(len(changed_files), changed_lines)

    records: list[BugFixRecord] = []
    for file_path in changed_files:
        buggy_code = load_file_at_commit(repo_dir, buggy_commit, file_path)
        fixed_code = load_file_at_commit(repo_dir, fixed_commit, file_path)
        if not buggy_code or not fixed_code or buggy_code == fixed_code:
            continue

        relative_name = file_path.replace("/", ":")
        records.append(
            BugFixRecord(
                id=f"bugsinpy:{project_name}:{bug_dir.name}:{relative_name}",
                source_dataset="bugsinpy",
                source_split="train",
                language="python",
                task_family="general_python",
                repository=project_info.get("github_url", "").removeprefix("https://github.com/").rstrip("/"),
                instance_id=f"bugsinpy_{project_name}_{bug_dir.name}",
                buggy_code=buggy_code,
                fixed_code=fixed_code,
                file_path=file_path,
                function_name="",
                prompt="",
                bug_type="unknown",
                failure_signal=" ; ".join(tests),
                tests=tests,
                commit_buggy=buggy_commit,
                commit_fixed=fixed_commit,
                metadata={
                    "scope": scope,
                    "files_changed": len(changed_files),
                    "changed_lines": changed_lines,
                    "has_repro": bool(tests),
                    "synthetic": False,
                    "generated": False,
                    "framework_heavy": False,
                    "non_code_fix_only": False,
                    "source_test_file": bug_info.get("test_file", ""),
                    "python_version": bug_info.get("python_version", ""),
                },
            )
        )
    return records


def discover_projects(bugsinpy_root: Path, selected_projects: list[str] | None) -> list[Path]:
    projects_root = bugsinpy_root / "projects"
    projects = [path for path in projects_root.iterdir() if path.is_dir()]
    if selected_projects:
        wanted = set(selected_projects)
        projects = [path for path in projects if path.name in wanted]
    return sorted(projects)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugsinpy-root", default="data/external_sources/BugsInPy")
    parser.add_argument("--repo-cache-root", default="data/external_sources/repo_cache")
    parser.add_argument("--output-path", default="data/external_sources/bugsinpy_normalized.jsonl")
    parser.add_argument("--projects", nargs="+", default=None)
    parser.add_argument("--limit-bugs", type=int, default=None)
    args = parser.parse_args()

    bugsinpy_root = Path(args.bugsinpy_root)
    repo_cache_root = Path(args.repo_cache_root)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_records = 0
    written = 0

    with output_path.open("w") as handle:
        for project_dir in discover_projects(bugsinpy_root, args.projects):
            project_info = parse_shell_kv(project_dir / "project.info")
            github_url = project_info.get("github_url", "")
            if not github_url:
                print(f"[WARN] Missing github_url for {project_dir.name}")
                continue

            repo_dir = ensure_repo(repo_cache_root, project_dir.name, github_url)
            if repo_dir is None:
                continue

            bug_dirs = sorted(
                (
                    path
                    for path in (project_dir / "bugs").iterdir()
                    if path.is_dir() and path.name.isdigit()
                ),
                key=lambda path: int(path.name),
            )
            if args.limit_bugs:
                bug_dirs = bug_dirs[: args.limit_bugs]

            for bug_dir in bug_dirs:
                records = build_records_for_bug(project_dir.name, project_dir, bug_dir, repo_dir)
                total_records += len(records)
                for record in records:
                    handle.write(json.dumps(asdict(record)) + "\n")
                    written += 1

    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "records_written": written,
                "records_seen": total_records,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
