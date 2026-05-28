from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.repair_baseline import repair_without_rag
from src.models.repair_rag import repair_with_rag
from src.retrieval.failure_state import make_failure_state


MAX_RAG_REPAIR_ATTEMPTS = 2


class InfrastructureFailure(Exception):
    pass


def write_trace(
    trace_dir: str | None,
    mode: str,
    case_id: str,
    attempt: int,
    payload: dict,
) -> None:
    if not trace_dir:
        return
    os.makedirs(trace_dir, exist_ok=True)
    trace_path = Path(trace_dir) / f"{mode}__{case_id}__attempt{attempt}.json"
    trace_path.write_text(json.dumps(payload, indent=2))


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


def load_dataset(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


def load_cases(path: str, projects_filter: set[str] | None = None) -> list[dict]:
    payload = load_dataset(path)
    if isinstance(payload, dict) and "cases" in payload:
        cases = [case for case in payload["cases"] if case.get("included", True)]
        if projects_filter:
            cases = [case for case in cases if case.get("repository") in projects_filter]
        return cases
    if isinstance(payload, list):
        return iter_supported_cases(payload, projects_filter=projects_filter)
    raise ValueError(f"Unsupported PyBugHive dataset shape: {path}")


def looks_like_test_file(file_path: str) -> bool:
    lowered = file_path.lower()
    name = Path(file_path).name.lower()
    if "/test" in lowered or "/tests/" in lowered:
        return True
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    return False


def supported_source_files(issue: dict) -> list[dict]:
    commit = issue["commits"][0]
    return [
        item
        for item in commit["stat"]["files"]
        if item["filename"].endswith(".py") and not looks_like_test_file(item["filename"])
    ]


def iter_supported_cases(dataset: list[dict], projects_filter: set[str] | None = None) -> list[dict]:
    supported: list[dict] = []
    for project in dataset:
        repository = project["repository"]
        if projects_filter and repository not in projects_filter:
            continue
        for issue in project["issues"]:
            commit = issue["commits"][0]
            source_files = supported_source_files(issue)
            test_steps = issue.get("testSteps") or issue.get("testStepsFull") or ""
            if not issue.get("manuallyChecked"):
                continue
            if len(source_files) != 1:
                continue
            if not commit.get("parents"):
                continue
            if not test_steps.strip():
                continue
            supported.append(
                {
                    "username": project["username"],
                    "repository": repository,
                    "issue_id": issue["id"],
                    "title": issue.get("title", ""),
                    "labels": issue.get("labels", ""),
                    "buggy_commit": commit["parents"],
                    "fixed_commit": commit["hash"],
                    "file_path": source_files[0]["filename"],
                    "test_steps": test_steps,
                    "test_steps_full": issue.get("testStepsFull", ""),
                    "install_steps": issue.get("installSteps") or project.get("installSteps", ""),
                }
            )
    return supported


def load_existing_results(path: str) -> list[dict]:
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


def save_results(path: str, results: list[dict]) -> None:
    with open(path, "w") as handle:
        json.dump(results, handle, indent=2)


def checkout_case(repo_dir: Path, case: dict, workspace_root: Path) -> Path:
    case_dir = workspace_root / f"{case['repository']}-{case['issue_id']}"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    clone = subprocess.run(
        ["git", "clone", str(repo_dir), str(case_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if clone.returncode != 0:
        raise RuntimeError(f"git clone failed: {clone.stderr.strip()}")

    checkout = run_git(case_dir, "checkout", "-q", case["buggy_commit"], "--force")
    if checkout.returncode != 0:
        raise RuntimeError(f"git checkout failed: {checkout.stderr.strip()}")
    return case_dir


def read_file(path: Path) -> str:
    return path.read_text()


def write_file(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def rewrite_command(step: str, pipenv_bin: str) -> str:
    stripped = step.strip()
    if not stripped:
        return stripped

    typo_rewrites = (
        (r"^ppipenv\b", "pipenv"),
        (r"^pipenev\b", "pipenv"),
        (r"\bpipenv\s+runtimeout\b", "pipenv run timeout"),
        (r"\bpipenv\s+run\s+ython\b", "pipenv run python"),
    )
    for pattern, replacement in typo_rewrites:
        stripped = re.sub(pattern, replacement, stripped)

    if stripped.startswith("pipenv run timeout "):
        tokens = shlex.split(stripped)
        if len(tokens) >= 5:
            stripped = shlex.join(tokens[:2] + tokens[4:])
    elif stripped.startswith("timeout "):
        tokens = shlex.split(stripped)
        if len(tokens) >= 3:
            stripped = shlex.join(tokens[2:])

    if stripped.startswith("pipenv "):
        if stripped.startswith("pipenv install "):
            package_args = stripped[len("pipenv install "):].strip()
            return f"{pipenv_bin} run python -m pip install {package_args}"
        if stripped.startswith("pipenv run pytest"):
            pytest_args = stripped[len("pipenv run pytest"):].strip()
            suffix = f" {pytest_args}" if pytest_args else ""
            return f"{pipenv_bin} run python -m pytest{suffix}"
        return f"{pipenv_bin} {stripped[len('pipenv '):]}"
    return stripped


def enrich_build_env(env: dict[str, str]) -> dict[str, str]:
    local_env = env.copy()
    openssl_prefixes = [
        Path("/opt/homebrew/opt/openssl@3"),
        Path("/opt/homebrew/opt/openssl@1.1"),
        Path("/usr/local/opt/openssl@1.1"),
    ]
    for prefix in openssl_prefixes:
        header = prefix / "include" / "openssl" / "opensslv.h"
        if not header.exists():
            continue
        include_dir = prefix / "include"
        lib_dir = prefix / "lib"
        pkgconfig_dir = lib_dir / "pkgconfig"
        local_env["OPENSSL_DIR"] = str(prefix)
        local_env["CPPFLAGS"] = f"-I{include_dir} {local_env.get('CPPFLAGS', '')}".strip()
        local_env["CFLAGS"] = f"-I{include_dir} {local_env.get('CFLAGS', '')}".strip()
        local_env["LDFLAGS"] = f"-L{lib_dir} {local_env.get('LDFLAGS', '')}".strip()
        local_env["LIBRARY_PATH"] = f"{lib_dir}:{local_env.get('LIBRARY_PATH', '')}".strip(":")
        local_env["CPATH"] = f"{include_dir}:{local_env.get('CPATH', '')}".strip(":")
        local_env["PKG_CONFIG_PATH"] = f"{pkgconfig_dir}:{local_env.get('PKG_CONFIG_PATH', '')}".strip(":")
        break
    return local_env


def extract_requested_python_version(install_steps: str) -> str | None:
    match = re.search(r"pipenv\s+--python\s+([0-9]+\.[0-9]+)", install_steps)
    if match:
        return match.group(1)
    return None


def resolve_pipenv_python(case_dir: Path, pipenv_bin: str, env: dict[str, str]) -> Path | None:
    in_project_python = case_dir.resolve() / ".venv" / "bin" / "python"
    if in_project_python.exists():
        return in_project_python

    result = subprocess.run(
        [pipenv_bin, "--venv"],
        cwd=case_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        return None

    venv_path = Path(result.stdout.strip())
    python_path = venv_path / "bin" / "python"
    if python_path.exists():
        return python_path
    return None


def normalize_pipenv_tooling(case_dir: Path, pipenv_bin: str, env: dict[str, str], timeout: int, python_version: str | None) -> subprocess.CompletedProcess | None:
    if python_version is None:
        return None
    major_minor = tuple(int(part) for part in python_version.split("."))
    venv_python = resolve_pipenv_python(case_dir, pipenv_bin, env)
    if venv_python is None:
        return subprocess.CompletedProcess([], 1, "", "Unable to locate pipenv virtualenv python.")

    if major_minor <= (3, 7):
        spec_args = ["pip<24.1", "setuptools<70"]
    elif major_minor <= (3, 8):
        spec_args = ["pip<25", "setuptools<76"]
    else:
        return None

    bootstrap_code = (
        "import ensurepip, pathlib, runpy, sys;"
        "bundle = pathlib.Path(ensurepip.__file__).resolve().parent / '_bundled';"
        "pip_wheels = sorted(bundle.glob('pip-*.whl'));"
        "sys.path.insert(0, str(pip_wheels[-1]));"
        "sys.argv = ['pip', 'install', '--force-reinstall', '--no-deps', *sys.argv[1:]];"
        "runpy.run_module('pip', run_name='__main__')"
    )
    cmd = [str(venv_python), "-c", bootstrap_code, *spec_args]
    result = subprocess.run(
        cmd,
        cwd=case_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        return result

    verify = subprocess.run(
        [
            str(venv_python),
            "-c",
            (
                "import pip, sys;"
                "assert tuple(int(p) for p in pip.__version__.split('.')[:2]) < (25, 0);"
                "print(pip.__version__)"
            ),
        ],
        cwd=case_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
        check=False,
    )
    return verify


def run_bundled_pip(venv_python: Path, cwd: Path, env: dict[str, str], timeout: int, pip_args: list[str]) -> subprocess.CompletedProcess:
    venv_root = venv_python.parent.parent
    local_env = env.copy()
    local_env["VIRTUAL_ENV"] = str(venv_root)
    local_env["PYTHONNOUSERSITE"] = "1"
    local_env["PIP_USER"] = "0"
    local_env["PATH"] = f"{venv_root / 'bin'}:{local_env.get('PATH', '')}"
    effective_args = list(pip_args)
    if effective_args and effective_args[0] == "install" and "--prefix" not in effective_args and "--target" not in effective_args:
        effective_args = ["install", "--prefix", str(venv_root), *effective_args[1:]]
    pip_code = (
        "import ensurepip, pathlib, runpy, sys;"
        "bundle = pathlib.Path(ensurepip.__file__).resolve().parent / '_bundled';"
        "pip_wheels = sorted(bundle.glob('pip-*.whl'));"
        "sys.path.insert(0, str(pip_wheels[-1]));"
        "sys.argv = ['pip', *sys.argv[1:]];"
        "runpy.run_module('pip', run_name='__main__')"
    )
    return subprocess.run(
        [str(venv_python), "-c", pip_code, *effective_args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=local_env,
        timeout=timeout,
        check=False,
    )


def run_pipenv_lock_install(case_dir: Path, pipenv_bin: str, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    venv_python = resolve_pipenv_python(case_dir, pipenv_bin, env)
    if venv_python is None:
        return subprocess.CompletedProcess([], 1, "", "Unable to locate pipenv virtualenv python.")

    requirements = subprocess.run(
        [pipenv_bin, "requirements"],
        cwd=case_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
        check=False,
    )
    if requirements.returncode != 0:
        return requirements

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write(requirements.stdout)
        temp_requirements = Path(handle.name)

    try:
        result = run_bundled_pip(
            venv_python=venv_python,
            cwd=case_dir,
            env=env,
            timeout=timeout,
            pip_args=["install", "-r", str(temp_requirements)],
        )
        if result.returncode == 0:
            return result
        conflict_markers = (
            "ResolutionImpossible",
            "conflicting dependencies",
            "Cannot install",
        )
        combined_output = f"{result.stdout}\n{result.stderr}"
        if any(marker in combined_output for marker in conflict_markers):
            return run_bundled_pip(
                venv_python=venv_python,
                cwd=case_dir,
                env=env,
                timeout=timeout,
                pip_args=[
                    "install",
                    "--use-deprecated=legacy-resolver",
                    "-r",
                    str(temp_requirements),
                ],
            )
        return result
    finally:
        temp_requirements.unlink(missing_ok=True)


def run_shell_steps(steps: str, cwd: Path, pipenv_bin: str, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    env = enrich_build_env(env)
    env.setdefault("PIPENV_VENV_IN_PROJECT", "1")
    env.setdefault("PIPENV_IGNORE_VIRTUALENVS", "1")
    last_result = subprocess.CompletedProcess([], 0, "", "")
    python_version = extract_requested_python_version(steps)
    normalized_tooling = False
    for raw_step in steps.splitlines():
        if not normalized_tooling and python_version and resolve_pipenv_python(cwd, pipenv_bin, env) is not None:
            compat_result = normalize_pipenv_tooling(cwd, pipenv_bin, env, timeout, python_version)
            normalized_tooling = True
            if compat_result is not None and compat_result.returncode != 0:
                return compat_result
        step = rewrite_command(raw_step, pipenv_bin)
        if not step:
            continue
        use_bundled_pip = False
        split_step = shlex.split(step)
        if python_version:
            major_minor = tuple(int(part) for part in python_version.split("."))
            if major_minor <= (3, 8):
                venv_python = resolve_pipenv_python(cwd, pipenv_bin, env)
                if venv_python is not None:
                    pip_prefixes = [
                        [pipenv_bin, "run", "python", "-m", "pip"],
                        [pipenv_bin, "run", "pip"],
                    ]
                    for prefix in pip_prefixes:
                        if split_step[: len(prefix)] == prefix:
                            pip_args = split_step[len(prefix):]
                            last_result = run_bundled_pip(venv_python, cwd, env, timeout, pip_args)
                            use_bundled_pip = True
                            break
                    if not use_bundled_pip and split_step == [pipenv_bin, "install"]:
                        last_result = run_pipenv_lock_install(cwd, pipenv_bin, env, timeout)
                        use_bundled_pip = True
        if not use_bundled_pip:
            last_result = subprocess.run(
                step,
                cwd=cwd,
                text=True,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=timeout,
                check=False,
            )
        if last_result.returncode != 0:
            break
    return last_result


def summarize_failure_output(stdout: str, stderr: str, max_lines: int = 25) -> str:
    lines: list[str] = []
    for source in (stdout, stderr):
        for line in source.splitlines():
            stripped = line.rstrip()
            if not stripped:
                continue
            lines.append(stripped)
    return "\n".join(lines[:max_lines])


def normalize_repair_result(result) -> tuple[str, dict | None]:
    if isinstance(result, dict):
        code = result.get("code")
        if not isinstance(code, str):
            raise ValueError("repair debug result missing code")
        return code, result
    if not isinstance(result, str):
        raise ValueError("repair result must be a string")
    return result, None


def collect_failure_signal(case_dir: Path, case: dict, pipenv_bin: str, timeout: int) -> str:
    env = os.environ.copy()
    result = run_shell_steps(case["test_steps"], case_dir, pipenv_bin, env, timeout)
    summary = summarize_failure_output(result.stdout, result.stderr)
    if result.returncode == 0:
        return "Original buggy code unexpectedly passed the configured test steps."
    if summary:
        return f"Observed failing signal:\n{summary}"
    return "Configured tests failed, but no detailed output was captured."


def build_followup_failure_signal(prior_signal: str, stdout: str, stderr: str) -> str:
    summary = summarize_failure_output(stdout, stderr)
    if not summary:
        summary = "The previous repair still failed, but no detailed output was captured."
    return f"{prior_signal}\n\nThe previous repair attempt still fails.\nNew failing signal:\n{summary}"


def install_case(case_dir: Path, case: dict, pipenv_bin: str, timeout: int) -> tuple[bool, str]:
    steps = case["install_steps"].strip()
    if not steps:
        return True, ""
    env = os.environ.copy()
    result = run_shell_steps(steps, case_dir, pipenv_bin, env, timeout)
    ok = result.returncode == 0
    output = summarize_failure_output(result.stdout, result.stderr)
    return ok, output


def evaluate_case(
    case: dict,
    repair_fn,
    mode: str,
    repo_cache_root: Path,
    workspace_root: Path,
    pipenv_bin: str,
    install_timeout: int,
    test_timeout: int,
    model: str | None = None,
    retrieval_profile: str | None = None,
    index_dir: str | None = None,
    skip_install: bool = False,
    trace_dir: str | None = None,
    rag_max_attempts: int = MAX_RAG_REPAIR_ATTEMPTS,
    retrieval_variant: str = "structured",
    include_case_metadata: bool = True,
    disabled_components: frozenset[str] | None = None,
) -> tuple[bool, str]:
    repo_dir = ensure_repo(repo_cache_root, case["username"], case["repository"])
    if repo_dir is None:
        raise InfrastructureFailure(f"Repo unavailable for {case['repository']}")

    case_dir = checkout_case(repo_dir, case, workspace_root)
    if not skip_install:
        install_ok, install_output = install_case(case_dir, case, pipenv_bin, install_timeout)
        if not install_ok:
            return False, f"[INSTALL FAILED]\n{install_output}"

    target_file = case_dir / case["file_path"]
    buggy_code = read_file(target_file)
    failure_signal = collect_failure_signal(case_dir, case, pipenv_bin, test_timeout)
    case_context = (
        f"Issue title: {case['title']}\n"
        f"Repository file: {case['file_path']}\n"
    )
    current_code = buggy_code
    current_signal = f"{case_context}\n{failure_signal}" if include_case_metadata else failure_signal
    current_failure_state = make_failure_state(current_signal, current_code).to_dict()
    max_attempts = max(1, rag_max_attempts) if mode == "rag" else 1
    case_id = f"{case['repository']}-{case['issue_id']}"

    for attempt in range(1, max_attempts + 1):
        repair_debug = None
        try:
            if mode == "rag":
                repaired = repair_fn(
                    current_code,
                    description=current_signal,
                    model=model,
                    retrieval_profile=retrieval_profile,
                    index_dir=index_dir,
                    retrieval_variant=retrieval_variant,
                    failure_state=current_failure_state,
                    return_debug=bool(trace_dir),
                    disabled_components=disabled_components,
                )
            else:
                repaired = repair_fn(
                    current_code,
                    description=current_signal,
                    model=model,
                    return_debug=bool(trace_dir),
                )
        except Exception as exc:
            if exc.__class__.__name__ in {"APIConnectionError", "APITimeoutError"}:
                raise InfrastructureFailure(str(exc)) from exc
            if trace_dir:
                write_trace(
                    trace_dir,
                    mode,
                    case_id,
                    attempt,
                    {
                        "case_id": case_id,
                        "mode": mode,
                        "attempt": attempt,
                        "repository": case["repository"],
                        "issue_id": case["issue_id"],
                        "file_path": case["file_path"],
                        "title": case["title"],
                        "buggy_code": current_code,
                        "failure_signal": current_signal,
                        "failure_state": current_failure_state,
                        "include_case_metadata": include_case_metadata,
                        "repair_exception": str(exc),
                        "repair_traceback": traceback.format_exc(),
                    },
                )
            raise

        repaired_code, repair_debug = normalize_repair_result(repaired)
        if repair_debug and repair_debug.get("patch_apply_status") == "rejected":
            summary = f"[PATCH REJECTED]\n{repair_debug.get('patch_rejection_reason') or 'unknown reason'}"
            trace_payload = {
                "case_id": case_id,
                "mode": mode,
                "attempt": attempt,
                "repository": case["repository"],
                "issue_id": case["issue_id"],
                "title": case["title"],
                "file_path": case["file_path"],
                "workspace_case_dir": str(case_dir.resolve()),
                "buggy_code": current_code,
                "failure_signal": current_signal,
                "failure_state": current_failure_state,
                "include_case_metadata": include_case_metadata,
                "generated_code": repaired_code,
                "test_command": case["test_steps"],
                "test_returncode": None,
                "test_stdout": "",
                "test_stderr": summary,
                "test_summary": summary,
                "pass": False,
                "prompt": repair_debug.get("prompt"),
                "messages": repair_debug.get("messages"),
                "retrieved_examples": repair_debug.get("retrieved_examples"),
                "retrieval_variant": repair_debug.get("retrieval_variant"),
                "retrieval_debug": repair_debug.get("retrieval_debug"),
                "patch_snippets": repair_debug.get("patch_snippets"),
                "patch_schema_version": repair_debug.get("patch_schema_version"),
                "patch_validation_retries": repair_debug.get("patch_validation_retries"),
                "patch_attempts": repair_debug.get("patch_attempts"),
                "patch_raw_response": repair_debug.get("patch_raw_response"),
                "patch_edits": repair_debug.get("patch_edits"),
                "patch_apply_status": repair_debug.get("patch_apply_status"),
                "patch_applied_edits": repair_debug.get("patch_applied_edits"),
                "patch_rejection_reason": repair_debug.get("patch_rejection_reason"),
                "generation_temperature": repair_debug.get("generation_temperature"),
                "strategy_note": repair_debug.get("strategy_note"),
            }
            write_trace(trace_dir, mode, case_id, attempt, trace_payload)
            return False, summary

        write_file(target_file, repaired_code)
        env = os.environ.copy()
        result = run_shell_steps(case["test_steps"], case_dir, pipenv_bin, env, test_timeout)
        summary = summarize_failure_output(result.stdout, result.stderr)
        trace_payload = {
            "case_id": case_id,
            "mode": mode,
            "attempt": attempt,
            "repository": case["repository"],
            "issue_id": case["issue_id"],
            "title": case["title"],
            "file_path": case["file_path"],
            "workspace_case_dir": str(case_dir.resolve()),
            "buggy_code": current_code,
            "failure_signal": current_signal,
            "failure_state": current_failure_state,
            "include_case_metadata": include_case_metadata,
            "generated_code": repaired_code,
            "test_command": case["test_steps"],
            "test_returncode": result.returncode,
            "test_stdout": result.stdout,
            "test_stderr": result.stderr,
            "test_summary": summary,
            "pass": result.returncode == 0,
        }
        if repair_debug:
            trace_payload.update(
                {
                    "prompt": repair_debug.get("prompt"),
                    "messages": repair_debug.get("messages"),
                    "retrieved_examples": repair_debug.get("retrieved_examples"),
                    "retrieval_variant": repair_debug.get("retrieval_variant"),
                    "retrieval_debug": repair_debug.get("retrieval_debug"),
                    "patch_snippets": repair_debug.get("patch_snippets"),
                    "patch_schema_version": repair_debug.get("patch_schema_version"),
                    "patch_validation_retries": repair_debug.get("patch_validation_retries"),
                    "patch_attempts": repair_debug.get("patch_attempts"),
                    "patch_raw_response": repair_debug.get("patch_raw_response"),
                    "patch_edits": repair_debug.get("patch_edits"),
                    "patch_apply_status": repair_debug.get("patch_apply_status"),
                    "patch_applied_edits": repair_debug.get("patch_applied_edits"),
                    "patch_rejection_reason": repair_debug.get("patch_rejection_reason"),
                    "generation_temperature": repair_debug.get("generation_temperature"),
                    "strategy_note": repair_debug.get("strategy_note"),
                }
            )
        write_trace(trace_dir, mode, case_id, attempt, trace_payload)
        if result.returncode == 0:
            return True, ""

        if attempt < max_attempts:
            current_code = repaired_code
            current_signal = build_followup_failure_signal(current_signal, result.stdout, result.stderr)
            current_failure_state = make_failure_state(current_signal, current_code).to_dict()
            continue

        return False, summary

    return False, ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "rag"], default="rag")
    parser.add_argument("--model", default=None)
    parser.add_argument("--dataset-json", default="data/external_sources/PyBugHive/dataset/pybughive_current.json")
    parser.add_argument("--repo-cache-root", default="data/external_sources/repo_cache")
    parser.add_argument("--workspace-root", default="temp_pybughive_eval")
    parser.add_argument("--results-path", default=None)
    parser.add_argument("--retrieval-profile", default=None)
    parser.add_argument("--retrieval-index-dir", default=None)
    parser.add_argument("--projects", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pipenv-bin", default=os.getenv("PYBUGHIVE_PIPENV", "pipenv"))
    parser.add_argument("--install-timeout", type=int, default=1800)
    parser.add_argument("--test-timeout", type=int, default=600)
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--list-supported", action="store_true")
    parser.add_argument("--trace-dir", default=None)
    parser.add_argument("--issue-ids", nargs="+", type=int, default=None)
    parser.add_argument("--rag-max-attempts", type=int, default=MAX_RAG_REPAIR_ATTEMPTS)
    parser.add_argument(
        "--retrieval-variant",
        choices=["structured", "code_only", "raw_text", "raw_text_rerank"],
        default="structured",
    )
    parser.add_argument(
        "--include-case-metadata",
        action="store_true",
        default=True,
        help="Include issue title and repository file in the repair description.",
    )
    parser.add_argument(
        "--no-case-metadata",
        action="store_false",
        dest="include_case_metadata",
        help="Remove issue title and repository file from the repair description.",
    )
    parser.add_argument(
        "--paper-primary",
        action="store_true",
        help="Use the paper primary setting: one attempt and no issue-title/file-path conditioning.",
    )
    args = parser.parse_args()

    if args.paper_primary:
        args.rag_max_attempts = 1
        args.include_case_metadata = False

    projects_filter = set(args.projects) if args.projects else None
    cases = load_cases(args.dataset_json, projects_filter=projects_filter)
    if args.issue_ids:
        issue_filter = set(args.issue_ids)
        cases = [case for case in cases if case["issue_id"] in issue_filter]
    if args.limit:
        cases = cases[: args.limit]

    if args.list_supported:
        print(json.dumps({"supported_cases": len(cases), "examples": cases[:10]}, indent=2))
        return

    results_path = args.results_path or f"experiments/pybughive_{args.mode}.json"
    Path(results_path).parent.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(args.workspace_root)
    workspace_root.mkdir(parents=True, exist_ok=True)
    repo_cache_root = Path(args.repo_cache_root)

    repair_fn = repair_without_rag if args.mode == "baseline" else repair_with_rag
    results = load_existing_results(results_path)
    completed = {item["case_id"] for item in results}

    print(f"Detected {len(cases)} supported PyBugHive cases.")
    for case in cases:
        case_id = f"{case['repository']}-{case['issue_id']}"
        if case_id in completed:
            continue
        print(f"\n=== {case_id} ({args.mode}) ===")
        try:
            ok, detail = evaluate_case(
                case=case,
                repair_fn=repair_fn,
                mode=args.mode,
                repo_cache_root=repo_cache_root,
                workspace_root=workspace_root,
                pipenv_bin=args.pipenv_bin,
                install_timeout=args.install_timeout,
                test_timeout=args.test_timeout,
                model=args.model,
                retrieval_profile=args.retrieval_profile or ("repair_clean" if args.mode == "rag" else None),
                index_dir=args.retrieval_index_dir,
                skip_install=args.skip_install,
                trace_dir=args.trace_dir,
                rag_max_attempts=args.rag_max_attempts,
                retrieval_variant=args.retrieval_variant,
                include_case_metadata=args.include_case_metadata,
            )
        except InfrastructureFailure as exc:
            print(f"[ABORT] Infrastructure failure: {exc}")
            break
        except Exception as exc:
            ok = False
            detail = f"[ERROR] {exc}\n{traceback.format_exc()}"

        print("PASS" if ok else "FAIL")
        if detail:
            print(detail)
        results.append(
            {
                "case_id": case_id,
                "repository": case["repository"],
                "issue_id": case["issue_id"],
                "file_path": case["file_path"],
                "retrieval_variant": args.retrieval_variant if args.mode == "rag" else None,
                "include_case_metadata": args.include_case_metadata,
                "rag_max_attempts": args.rag_max_attempts if args.mode == "rag" else None,
                "pass": ok,
                "detail": detail,
            }
        )
        completed.add(case_id)
        save_results(results_path, results)

    total = len(results)
    passed = sum(1 for item in results if item["pass"])
    print(json.dumps({"results_path": results_path, "passed": passed, "total": total}, indent=2))


if __name__ == "__main__":
    main()
