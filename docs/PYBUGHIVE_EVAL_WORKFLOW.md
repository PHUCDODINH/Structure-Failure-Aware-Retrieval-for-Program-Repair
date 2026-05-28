# PyBugHive Evaluation Workflow

This repo now includes a PyBugHive setup path for evaluating the current repair system on held-out Python bugs.

Files:
- Evaluator: `src/eval/evaluate_pybughive.py`
- Normalizer: `src/datasets/convert_pybughive.py`

## Supported evaluation subset

The evaluator intentionally restricts itself to bugs that are easier to run reproducibly:
- manually checked issues only
- exactly one changed non-test Python source file
- a recorded parent commit and fixed commit
- non-empty test steps

Current supported case count on the local `pybughive_current.json` metadata:
- `116`

## List supported cases

```bash
.venv312/bin/python src/eval/evaluate_pybughive.py --list-supported
```

## Normalize PyBugHive into the external corpus schema

```bash
.venv312/bin/python src/datasets/convert_pybughive.py \
  --dataset-json data/external_sources/PyBugHive/dataset/pybughive_current.json \
  --repo-cache-root data/external_sources/repo_cache \
  --output-path data/external_sources/pybughive_normalized.jsonl
```

## Run baseline evaluation

```bash
.venv312/bin/python src/eval/evaluate_pybughive.py \
  --mode baseline \
  --model gpt-4o \
  --results-path experiments/pybughive_baseline.json
```

## Run RAG evaluation

```bash
.venv312/bin/python src/eval/evaluate_pybughive.py \
  --mode rag \
  --model gpt-4o \
  --retrieval-profile repair_clean \
  --results-path experiments/pybughive_rag.json
```

## Important environment note

PyBugHive install steps commonly use `pipenv --python 3.7` or other older Python versions.
On the current machine:
- `pipenv` is not installed by default
- only `Python 3.13.5` is currently available from the shell

That means a live PyBugHive run will usually require:
- installing `pipenv`
- having the requested project Python versions available

The evaluator supports overriding the pipenv executable:

```bash
.venv312/bin/python src/eval/evaluate_pybughive.py \
  --mode baseline \
  --pipenv-bin /path/to/pipenv
```

If you need a quick metadata-only sanity check without installs:

```bash
.venv312/bin/python src/eval/evaluate_pybughive.py \
  --list-supported \
  --projects black
```
