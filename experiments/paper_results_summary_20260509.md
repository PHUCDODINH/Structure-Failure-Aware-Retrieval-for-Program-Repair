# Paper Results Summary - 2026-05-09

## Current Method State

- Retrieval profile: `repair_clean`
- Main model: `gpt-4o`
- Primary setting: single attempt, single candidate, `k=2`
- QuixBugs primary files: `experiments/paper_primary_quixbugs_gpt4o_v1_*.json`
- PyBugHive primary files: `experiments/paper_primary_pybughive_black_gpt4o_v3_*.json`
- Retrieval relevance file: `experiments/paper_retrieval_relevance_quixbugs_pybughive_v3.json`
- PyBugHive materialized retrieval dataset: `experiments/pybughive_black_frozen_v1_materialized_for_retrieval.json`
- PyBugHive case studies: `experiments/case_studies/pybughive_black_gpt4o_v3/`

## Model Robustness: QuixBugs Primary

### gpt-4o

| Variant | Passes | Total | Pass rate | Delta vs baseline |
|---|---:|---:|---:|---:|
| baseline | 35 | 40 | 87.5% | 0 |
| code_only | 37 | 40 | 92.5% | +2 |
| raw_text | 35 | 40 | 87.5% | 0 |
| raw_text_rerank | 34 | 40 | 85.0% | -1 |
| structured | 37 | 40 | 92.5% | +2 |

### gpt-4.1

| Variant | Passes | Total | Pass rate | Delta vs baseline |
|---|---:|---:|---:|---:|
| baseline | 36 | 40 | 90.0% | 0 |
| code_only | 35 | 40 | 87.5% | -1 |
| raw_text | 34 | 40 | 85.0% | -2 |
| raw_text_rerank | 36 | 40 | 90.0% | 0 |
| structured | 35 | 40 | 87.5% | -1 |

### gpt-4o-mini

| Variant | Passes | Total | Pass rate | Delta vs baseline |
|---|---:|---:|---:|---:|
| baseline | 33 | 40 | 82.5% | 0 |
| code_only | 33 | 40 | 82.5% | 0 |
| raw_text | 31 | 40 | 77.5% | -2 |
| raw_text_rerank | 32 | 40 | 80.0% | -1 |
| structured | 30 | 40 | 75.0% | -3 |

Interpretation: the structured downstream gain is not model-universal. It helps on `gpt-4o`, does not beat baseline on `gpt-4.1`, and hurts `gpt-4o-mini` in the primary single-candidate setting. This weakens any paper claim based only on downstream pass rate; the defensible claim still needs to center on retrieval relevance plus carefully scoped downstream evidence.

## Table 1 / Table 4: Retrieval Relevance

### QuixBugs

| Variant | Top-1 tag | Top-2 tag | Top-5 tag | Scope match | Symbol |
|---|---:|---:|---:|---:|---:|
| code_only | 0.272 | 0.237 | 0.218 | 0.100 | 0.017 |
| raw_text | 0.228 | 0.232 | 0.221 | 0.075 | 0.019 |
| raw_text_rerank | 0.247 | 0.221 | 0.195 | 0.100 | 0.016 |
| structured | 0.315 | 0.378 | 0.394 | 0.100 | 0.020 |

Interpretation: structured reranking gives the clearest retrieval-only improvement on QuixBugs, especially top-2/top-5 edit-pattern tag compatibility.

### PyBugHive-black

| Variant | Top-1 tag | Top-2 tag | Top-5 tag | Scope match | Symbol |
|---|---:|---:|---:|---:|---:|
| code_only | 0.166 | 0.158 | 0.123 | 0.529 | 0.063 |
| raw_text | 0.166 | 0.158 | 0.123 | 0.529 | 0.063 |
| raw_text_rerank | 0.147 | 0.120 | 0.114 | 0.529 | 0.063 |
| structured | 0.166 | 0.181 | 0.258 | 0.529 | 0.063 |

Interpretation: structured reranking improves PyBugHive top-5 tag compatibility, but not top-1. This supports a retrieval-pool relevance claim, not a strong downstream repair claim.

## Table 2: Primary Downstream Repair

### QuixBugs

| Variant | Passes | Total | Pass rate | Delta vs baseline |
|---|---:|---:|---:|---:|
| baseline | 35 | 40 | 87.5% | 0 |
| code_only | 37 | 40 | 92.5% | +2 |
| raw_text | 35 | 40 | 87.5% | 0 |
| raw_text_rerank | 34 | 40 | 85.0% | -1 |
| structured | 37 | 40 | 92.5% | +2 |

Interpretation: structured matches code-only downstream on QuixBugs but beats raw-text controls. The retrieval-only table is stronger than the pass-rate table for the structured-specific claim.

### PyBugHive-black

| Variant | Passes | Total | Pass rate | Patch-match errors |
|---|---:|---:|---:|---:|
| baseline | 23 | 34 | 67.6% | 2 |
| code_only | 12 | 34 | 35.3% | 6 |
| raw_text | 11 | 34 | 32.4% | 6 |
| raw_text_rerank | 11 | 34 | 32.4% | 6 |
| structured | 11 | 34 | 32.4% | 5 |

Interpretation: PyBugHive downstream RAG underperforms direct baseline. This benchmark should be treated as a stress-test/supporting evidence showing retrieval relevance does not automatically translate into repair success with the current large-file patch generator.

## Table 3: Field Ablation

QuixBugs active ablations:

| Condition | Passes | Total | Delta vs full |
|---|---:|---:|---:|
| full | 37 | 40 | 0 |
| no_contract_tags | 36 | 40 | -1 |
| no_suspicious_symbols | 36 | 40 | -1 |
| no_failure_mode | 36 | 40 | -1 |
| no_exception_type | 37 | 40 | 0 |

Interpretation: contract tags, suspicious symbols, and failure mode each show small downstream contribution on QuixBugs. Exception type does not matter on this benchmark.

## Table 6: QuixBugs Variance

| Variant | Pass counts | Mean pass rate | Std |
|---|---|---:|---:|
| baseline | 37, 35, 36, 36, 35 | 89.5% | 2.1% |
| code_only | 36, 36, 37, 36, 36 | 90.5% | 1.1% |
| raw_text | 37, 36, 37, 37, 35 | 91.0% | 2.2% |
| raw_text_rerank | 35, 35, 35, 36, 35 | 88.0% | 1.1% |
| structured | 37, 35, 36, 37, 37 | 91.0% | 2.2% |

Interpretation: structured and raw_text tie in mean downstream pass rate across repeated QuixBugs trials. The paper claim should emphasize retrieval relevance and controlled ablations, not only pass-rate superiority.

## Table 5: Stronger System Setting

Current-code rerun after changing candidate evaluation to evaluate all three candidates:

| Variant | Passes | Total | Pass rate | Delta vs baseline |
|---|---:|---:|---:|---:|
| baseline | 37 | 40 | 92.5% | 0 |
| code_only | 37 | 40 | 92.5% | 0 |
| raw_text | 36 | 40 | 90.0% | -1 |
| structured | 37 | 40 | 92.5% | 0 |

File: `experiments/paper_table5_quixbugs_gpt4o_v2_summary.json`

Interpretation: in the stronger three-candidate setting, structured ties baseline and code_only, and beats raw_text by one problem. This supports a conservative claim that structured reranking remains competitive in the stronger system, not that it dominates.

## Case Studies

Generated PyBugHive case studies:

- `win_structured__black-385.md`: structured passes while baseline/code_only/raw_text/raw_text_rerank fail.
- `loss_structured__black-130.md`: baseline passes while structured fails.
- `loss_structured__black-133.md`: baseline passes while structured fails.
- `interesting_tie__black-334.md`: traces show different retrieval behavior with tied pass outcome.

## Writing Readiness

Ready to write:

- Retrieval mechanism and structured-failure motivation.
- QuixBugs retrieval relevance and primary downstream results.
- QuixBugs field ablations.
- QuixBugs stronger-system Table 5 rerun.
- QuixBugs variance table.
- PyBugHive as a realistic-repo stress test.
- Trace-backed case study for one PyBugHive structured win and failure cases.

Not ready for a strong claim:

- PyBugHive downstream improvement. Current RAG variants are worse than baseline.
- General claim that structured RAG improves repair success across realistic repositories.
- Strong claim that structured reranking beats code-only downstream; on QuixBugs it ties code_only, and on PyBugHive it does not.

Recommended paper framing:

- Main contribution: structured failure-aware retrieval improves retrieval relevance and can improve/maintain downstream repair on controlled algorithmic bugs.
- Supporting negative result: in realistic large-file repair, retrieval relevance is not sufficient when the patch-generation/application layer is brittle.
- Future work or next experiment: decouple retrieval from patch application by using a stronger edit-generation backend or line-range-aware patch format.

## Patch-Layer Experiment: Strict Line-Range JSON

After adding the strict `line_range_v1` large-file patch contract, PyBugHive structured RAG was rerun on the frozen 34-case set.

| Variant | Passes | Total | Pass rate | Notes |
|---|---:|---:|---:|---|
| structured + strict line-range patch | 9 | 34 | 26.5% | `experiments/patch_line_range_pybughive_structured_full_gpt4o_v1.json` |
| structured + strict line-range patch + one validation retry | 11 | 34 | 32.4% | `experiments/patch_retry_pybughive_structured_full_gpt4o_v1.json` |
| structured + validation retry + verifier-feedback localization | 12 | 34 | 35.3% | `experiments/verifier_feedback_pybughive_structured_full_gpt4o_v1.json` plus rate-limit cleanup `experiments/verifier_feedback_pybughive_structured_ratelimit4_gpt4o_v1.json` |

Trace breakdown:

| Patch status | Count | Passes | Failures |
|---|---:|---:|---:|
| applied | 21 | 6 | 15 |
| rejected | 10 | 0 | 10 |
| missing whole-code path | 3 | 3 | 0 |

Interpretation: the strict line-range patch path improves trace quality and prevents invalid unchanged-code successes, but it lowers structured downstream performance compared with the previous PyBugHive structured result (`11/34`). This is evidence that stricter patch validation alone is not enough; the next useful patch-layer direction is likely a repair loop for rejected/applied-failing edits or a better edit-localization/prompting mechanism, not a full rerun of all variants under this strict contract.

Validation-retry result:

| Patch status | Count | Passes | Failures |
|---|---:|---:|---:|
| applied | 22 | 8 | 14 |
| rejected | 9 | 0 | 9 |
| missing whole-code path | 3 | 3 | 0 |

Interpretation: one validation retry recovers the strict-line-range result from `9/34` to `11/34`, tying the old structured PyBugHive result but not improving beyond it. In this full run, 9 cases used a second validation attempt but still ended rejected, so the remaining bottleneck is not only patch syntax/anchoring; many generated edits are either semantically wrong after applying or still cannot localize the correct span.

Verifier-feedback localization result:

The evaluator was run with `rag_max_attempts=2`, `--no-case-metadata`, strict line-range patches, and one patch-validation retry. A cleanup rerun was needed for four rate-limited cases; only `black-46` changed from rate-limit failure to pass. Corrected result: `12/34`.

| Signal | Count |
|---|---:|
| attempt-2 traces | 17 |
| attempt-2 passes | 2 |
| attempt-2 traces with referenced-line snippets | 15 |

Interpretation: verifier feedback creates the intended second-attempt localization behavior and gives a small improvement over single-attempt structured PyBugHive (`11/34` to `12/34`). The gain is too small to support a strong system-performance claim, but it is useful evidence for the paper's bottleneck story: failure-conditioned localization helps some cases, while many failures remain semantic edit-generation failures after a patch applies.
