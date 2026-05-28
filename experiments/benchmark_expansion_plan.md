# Benchmark Expansion Plan

## Track 1: PyBugHive Multi-Project, Project-Held-Out Retrieval

Use this as the main extra benchmark because it stays close to the current
repository-level repair setting while reducing the Black-only overfitting risk.

Prepared artifacts:

- Frozen candidate list: `experiments/pybughive_multiproject_frozen_v1.json`
- Held-out corpus: `data/corpora/repair_clean_holdout_pybughive_projects.jsonl`
- Held-out index profile: `repair_clean_holdout_pybughive_projects`
- Contamination rule: remove repair corpus entries from PyBugHive project families
  `black`, `pandas`, `jax`, `freqtrade`, `spacy`, `poetry`, `salt`,
  `cookiecutter`, `scrapy`, `discord.py`, and `numpy`.

Corpus filter summary:

- Input repair examples: 551
- Removed same-project examples: 274
- Remaining examples: 277
- Removed by available BugsInPy overlap: `pandas=193`, `scrapy=41`,
  `black=23`, `spacy=11`, `cookiecutter=6`

Recommended first smoke:

```bash
env TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 \
  .venv312/bin/python src/eval/evaluate_pybughive.py \
  --dataset-json experiments/pybughive_multiproject_frozen_v1.json \
  --projects jax \
  --limit 3 \
  --mode baseline \
  --model gpt-4o \
  --paper-primary \
  --results-path experiments/pybughive_multiproject_jax_smoke3_baseline_gpt4o.json
```

```bash
env TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 \
  .venv312/bin/python src/eval/evaluate_pybughive.py \
  --dataset-json experiments/pybughive_multiproject_frozen_v1.json \
  --projects jax \
  --limit 3 \
  --mode rag \
  --retrieval-variant structured \
  --retrieval-profile repair_clean_holdout_pybughive_projects \
  --model gpt-4o \
  --paper-primary \
  --results-path experiments/pybughive_multiproject_jax_smoke3_structured_gpt4o.json
```

If the smoke works, run full one-project comparisons first, one model/method at
a time. Prefer `jax` or `freqtrade` before `pandas` because they are smaller
and expose whether the setup works without committing to a long run.

## Track 2: HumanEvalFix-Style Appendix Benchmark

Use this only as an appendix/sanity benchmark unless a real HumanEvalFix repair
dataset is added. The local `data/humaneval/HumanEval.jsonl` file is code
generation, not bug repair, so it should not be presented as direct evidence
for program repair.

Required before running:

- Add a HumanEvalFix-style JSONL file with buggy code, tests, and expected
  entry point.
- Build or select a retrieval profile that excludes HumanEval-derived records.
- Use the same single-attempt setting as the primary paper table.

Decision rule:

- If the dataset is not real bug repair, do not include it in the main paper
  table.
- If it is synthetic HumanEval mutation repair, label it explicitly as
  synthetic and keep it secondary.
