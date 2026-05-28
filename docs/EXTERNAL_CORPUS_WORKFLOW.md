# External Corpus Workflow

This repo now supports benchmark-specific retrieval indexes backed by an external Python bug-fix corpus.

## 1. Normalize External Sources

Convert BugsInPy and PyBugHive into the normalized schema described in
[BUGFIX_CORPUS_SPEC.md](/Users/dodinhphuc/PycharmProjects/RAGtest/docs/BUGFIX_CORPUS_SPEC.md).

### BugsInPy

```bash
.venv312/bin/python src/datasets/convert_bugsinpy.py \
  --bugsinpy-root data/external_sources/BugsInPy \
  --repo-cache-root data/external_sources/repo_cache \
  --output-path data/external_sources/bugsinpy_normalized.jsonl
```

This script uses BugsInPy metadata plus upstream project repositories to extract
buggy and fixed Python file contents from the buggy and fixed commits.

Recommended normalized inputs:

- `data/external_sources/bugsinpy_normalized.jsonl`
- `data/external_sources/pybughive_normalized.jsonl`

## 2. Build Benchmark-Specific Corpora

```bash
.venv312/bin/python -m src.datasets.build_external_bugfix_corpora \
  --source-jsonl data/external_sources/bugsinpy_normalized.jsonl \
  --source-jsonl data/external_sources/pybughive_normalized.jsonl \
  --output-dir data/corpora
```

This produces:

- `data/corpora/humaneval_external_bugfix.jsonl`
- `data/corpora/mbpp_external_bugfix.jsonl`
- `data/corpora/quixbugs_external_bugfix.jsonl`
- `data/corpora/repair_external_bugfix.jsonl`

## 3. Build Retrieval Indexes

```bash
.venv312/bin/python -m src.retrieval.build_index \
  --input-path data/corpora/humaneval_external_bugfix.jsonl \
  --profile humaneval_clean

.venv312/bin/python -m src.retrieval.build_index \
  --input-path data/corpora/mbpp_external_bugfix.jsonl \
  --profile mbpp_clean

.venv312/bin/python -m src.retrieval.build_index \
  --input-path data/corpora/quixbugs_external_bugfix.jsonl \
  --profile quixbugs_clean

.venv312/bin/python -m src.retrieval.build_index \
  --input-path data/corpora/repair_external_bugfix.jsonl \
  --profile repair_clean
```

## 4. Evaluate with Clean Retrieval Profiles

HumanEval:

```bash
.venv312/bin/python src/eval/eval_humaneval.py \
  --mode rag \
  --model gpt-4o-mini \
  --retrieval-profile humaneval_clean \
  --out-path experiments/humaneval_rag_external.json
```

MBPP:

```bash
.venv312/bin/python src/eval/eval_mbpp.py \
  --mode rag \
  --model gpt-4o-mini \
  --retrieval-profile mbpp_clean \
  --results-path experiments/mbpp_rag_external.json
```

QuixBugs:

```bash
.venv312/bin/python src/eval/evaluate_quixbugs.py \
  --mode rag \
  --model gpt-4o-mini \
  --retrieval-profile repair_clean \
  --out-file experiments/quixbugs_rag_external.json
```

## Notes

- `legacy` still points to the current merged benchmark index in `data/index`.
- Clean profiles are isolated under `data/indexes/<profile>/`.
- If needed, you can override the index directory directly with `--retrieval-index-dir`.
