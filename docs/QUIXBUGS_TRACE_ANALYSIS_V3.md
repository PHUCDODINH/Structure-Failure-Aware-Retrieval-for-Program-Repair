# QuixBugs Trace Analysis V3

Model: `gpt-4o`

Artifacts from the latest traced `40/40` rerun:
- Baseline results: `experiments/quixbugs_baseline_gpt4o_external_40_trace3.json`
- RAG results: `experiments/quixbugs_rag_gpt4o_external_40_trace3.json`
- Baseline traces: `experiments/traces/quixbugs_40_baseline_host_v3/`
- RAG traces: `experiments/traces/quixbugs_40_rag_host_v3/`

Run summary:
- Baseline: `32/40`
- RAG: `36/40`
- Delta: `+4` for RAG

This is the strongest full traced QuixBugs result so far. The updated `repair_lesson` heuristic was active in this run, so the retrieved guidance is more specific than in the earlier trace reports.

## Swap summary

RAG-only wins:
- `find_first_in_sorted`
- `max_sublist_sum`
- `powerset`
- `reverse_linked_list`
- `shortest_path_length`

Baseline-only wins:
- `topological_ordering`

## RAG-only wins

### `find_first_in_sorted`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v3/baseline__find_first_in_sorted__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v3/rag__find_first_in_sorted__attempt2.json`

Observed difference:
- Baseline kept the binary-search structure but still failed the first-occurrence edge case.
- RAG used the second attempt plus failing-test feedback to tighten the left-boundary handling and return the earliest matching index.

Why RAG likely helped:
- the retry prompt included the exact failing assertion,
- and the retrieved lessons emphasized boundary and pointer-like state corrections.

### `max_sublist_sum`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v3/baseline__max_sublist_sum__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v3/rag__max_sublist_sum__attempt2.json`

Observed difference:
- Baseline returned the standard Kadane-style answer and failed the all-negative edge case.
- RAG added explicit empty-input handling and changed the return to `max(max_so_far, 0)`, matching QuixBugs' expected behavior.

Why RAG likely helped:
- the second RAG attempt saw the concrete failure,
- and the retrieved lessons specifically pushed boundary handling and accumulator corrections.

### `powerset`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v3/baseline__powerset__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v3/rag__powerset__attempt2.json`

Observed difference:
- Baseline produced the right subsets in the wrong order.
- RAG flipped the concatenation order on retry and matched the benchmark's expected output sequence.

Why RAG likely helped:
- the retry had assertion feedback showing an ordering mismatch,
- and the retrieved lessons now explicitly mention returned-expression / contract alignment instead of only generic control-flow text.

### `reverse_linked_list`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v3/baseline__reverse_linked_list__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v3/rag__reverse_linked_list__attempt1.json`

Observed difference:
- Baseline drifted to the generic linked-list attribute `next`.
- RAG preserved QuixBugs' actual field name `successor` and passed on the first attempt.

Why RAG likely helped:
- the retrieved lessons now call out data-model / attribute preservation directly,
- which appears to reduce schema drift toward common Python conventions.

### `shortest_path_length`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v3/baseline__shortest_path_length__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host_v3/rag__shortest_path_length__attempt1.json`

Observed difference:
- Baseline kept an explicit `distances` map and still failed the benchmark.
- RAG produced a simpler heap-based traversal that passed this slice without needing a retry.

Why RAG likely helped:
- the retrieved context seems to have nudged the model toward a smaller local fix instead of carrying unnecessary state,
- and the updated lessons emphasized output-contract alignment and collection-state updates.

## Baseline-only win

### `topological_ordering`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host_v3/baseline__topological_ordering__attempt1.json`
- RAG traces:
  - `experiments/traces/quixbugs_40_rag_host_v3/rag__topological_ordering__attempt1.json`
  - `experiments/traces/quixbugs_40_rag_host_v3/rag__topological_ordering__attempt2.json`

Observed difference:
- Baseline passed directly with a straightforward incremental ordering loop.
- RAG failed even after retry, producing an order that looked plausible but still violated the test expectation.

## Practical takeaway

V3 is the clearest traced result in favor of the current repair setup:
- RAG gained `+4` overall
- five RAG-only wins came from edge-case handling, return-contract correction, and schema-preserving repairs
- the only baseline-only win remained an ordering-sensitive algorithm (`topological_ordering`)

The strongest qualitative pattern in this run is that RAG helps most when the failing repair depends on:
- preserving local names or object structure,
- matching benchmark-specific return behavior,
- or correcting edge cases after a targeted retry.

The V3 trace JSON files contain the exact prompts, retrieved examples, generated code, and pytest output for each attempt, so they are the best artifacts to inspect when comparing baseline and RAG behavior side by side.
