# PyBugHive Project-Held-Out Evaluation Summary

Date: 2026-05-18

## Setup

- Model: `gpt-4o`
- Setting: paper-primary, single attempt, no issue-title/file-path conditioning
- Retrieval profile: `repair_clean_holdout_pybughive_projects`
- Held-out corpus size: 277 examples
- Held-out rule: removed all available BugsInPy entries matching PyBugHive project families
- Verified held-out index contamination: 0 excluded-project records

## Held-Out Corpus

- Original `repair_clean`: 551 examples
- Removed same-project examples: 274
- Remaining examples: 277
- Removed overlap by project: `pandas=193`, `scrapy=41`, `black=23`, `spacy=11`, `cookiecutter=6`

## Smoke Results

### `discord.py` project, 2 cases

| Variant | Pass / Total | Notes |
|---|---:|---|
| baseline | 1 / 2 | one strict patch rejection |
| code_only | 1 / 2 | one strict patch rejection |
| raw_text | 1 / 2 | one strict patch rejection |
| raw_text_rerank | 2 / 2 | both passed |
| structured | 1 / 2 | one strict patch rejection |

### Rejected smoke candidates

- `jax`: 3/3 install failures because cases attempt to build `jaxlib` with Bazel; not suitable as a first expansion benchmark on this machine.
- `cookiecutter`: install succeeded, but test import failed because the environment pulled `click 8.4.0`, which uses syntax incompatible with Python 3.8. Treat as environment failure unless dependency pinning is added.

## Black Held-Out Results

`black` has 34 supported cases. These results use the held-out profile, so Black BugsInPy examples are not retrievable.

| Variant | Pass / Total | Corrected Notes |
|---|---:|---|
| baseline | 23 / 34 | existing comparable paper-primary baseline; retrieval-independent |
| code_only | 23 / 34 | completed without infrastructure failures |
| structured | 23 / 34 | one rate-limit case rerun; rerun failed by patch rejection, so final remains 23 / 34 |
| raw_text_rerank | 12 / 34 | two rate-limit cases rerun; both failed by repair reasons, so final remains 12 / 34 |

Failure profile:

| Variant | Pass | Patch Rejected | Test Failed |
|---|---:|---:|---:|
| code_only | 23 | 7 | 4 |
| structured | 23 | 7 | 4 |
| raw_text_rerank | 12 | 16 | 6 |

## Current Interpretation

The held-out Black run changes the contamination story: removing same-project BugsInPy retrieval does not reduce structured RAG below the baseline on Black, but it also does not improve over code-only retrieval. This supports a narrower claim: the current structured retrieval is contamination-safe under project holdout, but downstream gains remain limited by patch conversion and model sensitivity.

The raw-text reranker is unstable. It won on the tiny `discord.py` smoke but collapsed on Black, mostly by increasing strict patch rejections.

## Remaining Evaluation

- Run Black held-out `raw_text` only if a complete five-variant held-out table is required.
- Add a runnable second non-Black project only if dependency setup can be stabilized. `discord.py` is currently usable but too small.
- HumanEvalFix is not runnable yet because no real repair-format HumanEvalFix dataset exists locally.
