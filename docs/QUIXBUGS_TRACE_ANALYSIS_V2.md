# QuixBugs Trace Analysis V2

Model: `gpt-4o`

Artifacts from the latest traced `40/40` rerun:
- Baseline results: `experiments/quixbugs_baseline_gpt4o_external_40_trace2.json`
- RAG results: `experiments/quixbugs_rag_gpt4o_external_40_trace2.json`
- Baseline traces: `experiments/traces/quixbugs_40_baseline_host_v2/`
- RAG traces: `experiments/traces/quixbugs_40_rag_host_v2/`

Run summary:
- Baseline: `33/40`
- RAG: `34/40`
- Delta: `+1` for RAG

## Swap summary

RAG-only wins:
- `max_sublist_sum`
- `powerset`
- `reverse_linked_list`

Baseline-only wins:
- `kheapsort`
- `topological_ordering`

## RAG-only wins

### `max_sublist_sum`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v2/baseline__max_sublist_sum__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v2/rag__max_sublist_sum__attempt2.json`

Observed difference:
- Baseline returned the usual Kadane-style variant that fails the all-negative edge case.
- RAG fixed the second-attempt failure by changing the return behavior to match the test expectation of `0` for `[-4, -4, -5]`.

Why RAG likely helped:
- the second RAG attempt included failing-test feedback,
- and the retrieved repair lessons emphasized boundary / returned-value corrections.

### `powerset`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v2/baseline__powerset__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v2/rag__powerset__attempt2.json`

Observed difference:
- Baseline produced the correct subsets in the wrong order.
- RAG changed the concatenation order on the second attempt and matched the expected sequence.

Why RAG likely helped:
- the second RAG attempt saw the assertion diff from the failed test,
- and the retrieved examples reinforced local control-flow / output-shape corrections instead of a full rewrite.

### `reverse_linked_list`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v2/baseline__reverse_linked_list__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v2/rag__reverse_linked_list__attempt1.json`

Observed difference:
- Baseline drifted to the common linked-list field name `next`.
- RAG preserved QuixBugs’ actual field name `successor` and passed.

Why RAG likely helped:
- the extra retrieved context appears to reduce schema drift toward generic conventions,
- keeping the repair aligned with the target code’s local naming.

## Baseline-only wins

### `kheapsort`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v2/baseline__kheapsort__attempt1.json`
- RAG traces:
  - `experiments/traces/quixbugs_40_rag_host_v2/rag__kheapsort__attempt1.json`
  - `experiments/traces/quixbugs_40_rag_host_v2/rag__kheapsort__attempt2.json`

Observed difference:
- Baseline passed directly.
- RAG failed even after a retry, still dropping the first element of the sorted output.

### `topological_ordering`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v2/baseline__topological_ordering__attempt1.json`
- RAG traces:
  - `experiments/traces/quixbugs_40_rag_host_v2/rag__topological_ordering__attempt1.json`
  - `experiments/traces/quixbugs_40_rag_host_v2/rag__topological_ordering__attempt2.json`

Observed difference:
- Baseline produced the expected order.
- RAG produced a valid-looking but wrong node order even after retry.

## Practical takeaway

This rerun repeats the same RAG-only win pattern seen earlier:
- `max_sublist_sum`
- `powerset`
- `reverse_linked_list`

That consistency matters more than the exact total. The latest traced run still shows:
- RAG helps most on edge-case correction and schema-preserving repair
- RAG can still hurt on ordering-sensitive algorithmic repairs like `topological_ordering`

The v2 trace JSON files contain the exact prompts, retrieved examples, generated code, and pytest output for each attempt, so they can be used directly for side-by-side prompt and code comparisons.
