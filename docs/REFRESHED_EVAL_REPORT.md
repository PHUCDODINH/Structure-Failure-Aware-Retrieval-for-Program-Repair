# Refreshed Evaluation Report

Date: 2026-03-11
Model: `gpt-4o`
Corpus: external clean bug-fix corpus

## Final Refreshed Results

| Benchmark | Baseline | RAG | Delta |
| --- | ---: | ---: | ---: |
| HumanEval | 137/164 | 138/164 | +1 |
| MBPP | 86/100 | 88/100 | +2 |
| QuixBugs | 26/30 | 28/30 | +2 |

Result files:
- HumanEval baseline: `experiments/humaneval_baseline_gpt4o_host_full.json`
- HumanEval RAG: `experiments/humaneval_rag_gpt4o_host_full.json`
- MBPP baseline: `experiments/mbpp_baseline_gpt4o_host_100.json`
- MBPP RAG: `experiments/mbpp_rag_gpt4o_host_100.json`
- QuixBugs baseline: `experiments/quixbugs_baseline_gpt4o_external_30_host.json`
- QuixBugs RAG: `experiments/quixbugs_rag_gpt4o_external_30_host.json`

## Previous Clean-Corpus Results

| Benchmark | Baseline | RAG | Delta |
| --- | ---: | ---: | ---: |
| HumanEval | 142/164 | 143/164 | +1 |
| MBPP | 56/100 | 54/100 | -2 |
| QuixBugs (older slice/config) | 25/30 | 28/30 | +3 |

Reference files:
- `experiments/humaneval_baseline_gpt4o_external_compare.json`
- `experiments/humaneval_rag_gpt4o_external_full.json`
- `experiments/mbpp_baseline_gpt4o_external_100.json`
- `experiments/mbpp_rag_gpt4o_external_100.json`
- `experiments/quixbugs_baseline_gpt4o_external_30_feedback.json`
- `experiments/quixbugs_rag_gpt4o_external_30_iterative.json`

## Main Interpretation

- HumanEval remains roughly neutral-to-slightly-positive for RAG.
- MBPP changed materially after evaluator and prompt fixes; RAG is now slightly positive instead of negative.
- QuixBugs remains the clearest win for the framework and is the strongest repair result.

## Important Caveat

Do not compare old and new absolute scores as if they were pure model gains:
- MBPP changed a lot because the evaluation harness and prompting were corrected.
- QuixBugs changed because the repair loop and failure-aware prompting were improved.
- HumanEval reruns used host-network execution and more robust checkpointing.

The defensible claim is:
- under the refreshed framework, RAG gives small but consistent gains on all three benchmarks.

The non-defensible claim is:
- the original framework already gave these gains.

## Recommended Research Framing

Use wording like:
- "RAG provided modest but consistent improvements after retrieval, prompting, and evaluation-quality fixes."
- "The largest benefit appeared on code repair (QuixBugs), with smaller gains on generation benchmarks."

Avoid wording like:
- "RAG substantially improves performance."
- "RAG consistently delivers large gains across benchmarks."
