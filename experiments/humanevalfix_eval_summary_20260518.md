# HumanEvalFix Evaluation Summary

Date: 2026-05-18

## Dataset Import

- Source: BigCode/OctoPack HumanEvalPack Python JSONL
- Local file: `data/humanevalfix/HumanEvalFix.jsonl`
- Tasks: 164
- Fields used: `declaration`, `buggy_solution`, `canonical_solution`, `test`,
  `entry_point`, `bug_type`, `failure_symptoms`

Sanity check:

- First 10 buggy solutions: 0 / 10 pass
- First 10 canonical solutions: 10 / 10 pass

## Evaluation Setup

- Model: `gpt-4o`
- Prompt mode: `tests`
- Baseline input: buggy function + bug type + failure symptoms + tests
- RAG input: same as baseline plus retrieved examples from `repair_clean`
- Retrieval profile: `repair_clean`
- Retrieval corpus source labels: `bugsinpy=551`
- HumanEval contamination in `repair_clean`: 0 matching records/mentions found

## Full Results

| Method | Pass / Total | Pass Rate |
|---|---:|---:|
| baseline | 132 / 164 | 80.5% |
| structured RAG | 126 / 164 | 76.8% |

## Model Comparison

| Model | Baseline | Structured RAG | Delta |
|---|---:|---:|---:|
| `gpt-4o` | 132 / 164 | 126 / 164 | -6 |
| `gpt-4.1` | 131 / 164 | 129 / 164 | -2 |
| `gpt-4o-mini` | 112 / 164 | 109 / 164 | -3 |

Pairwise by model:

| Model | RAG-only Wins | Baseline-only Wins | Both Fail |
|---|---:|---:|---:|
| `gpt-4o` | 2 | 8 | 30 |
| `gpt-4.1` | 3 | 5 | 30 |
| `gpt-4o-mini` | 7 | 10 | 45 |

Pairwise:

- RAG-only wins: `Python/93`, `Python/132`
- Baseline-only wins: `Python/33`, `Python/36`, `Python/46`, `Python/63`,
  `Python/83`, `Python/113`, `Python/116`, `Python/118`
- Both fail: 30 tasks

## By Bug Type

| Bug Type | Baseline | Structured RAG |
|---|---:|---:|
| excess logic | 26 / 31 | 23 / 31 |
| function misuse | 5 / 8 | 5 / 8 |
| missing logic | 22 / 33 | 22 / 33 |
| operator misuse | 20 / 25 | 19 / 25 |
| value misuse | 41 / 44 | 40 / 44 |
| variable misuse | 18 / 23 | 17 / 23 |

## Interpretation

HumanEvalFix is useful as a clean synthetic repair benchmark, but it currently
does not support the structured-RAG claim. Across `gpt-4o`, `gpt-4.1`, and
`gpt-4o-mini`, direct baseline is stronger than structured RAG. The negative
delta is smallest on `gpt-4.1` and largest on `gpt-4o`, but the trend is
consistent. This should be reported as an appendix/robustness result unless
later retrieval changes improve it.

The result is still valuable because the retrieval database is BugsInPy-only and
has no HumanEval records, so the benchmark is not contaminated by the current
RAG corpus.
