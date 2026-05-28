# QuixBugs Trace Analysis

Model: `gpt-4o`

Traced run artifacts:
- Baseline results: `experiments/quixbugs_baseline_gpt4o_external_40_trace.json`
- RAG results: `experiments/quixbugs_rag_gpt4o_external_40_trace.json`
- Baseline traces: `experiments/traces/quixbugs_40_baseline_host/`
- RAG traces: `experiments/traces/quixbugs_40_rag_host/`

Run summary:
- Baseline: `33/40`
- RAG: `33/40`

RAG-only wins:
- `max_sublist_sum`
- `powerset`
- `reverse_linked_list`

Baseline-only wins:
- `kheapsort`
- `knapsack`
- `topological_ordering`

## RAG-only wins

### `max_sublist_sum`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host/baseline__max_sublist_sum__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host/rag__max_sublist_sum__attempt2.json`

Code difference:
- Baseline returned the standard Kadane variant that fails all-negative input by returning `-4`.
- RAG second attempt added `return max(max_so_far, 0)`, matching the QuixBugs test expectation.

Prompt difference:
- Baseline prompt only contained the buggy code and failure signal.
- RAG attempt 2 also contained retrieved bug-fix snippets and the follow-up failing test output showing `expected = 0` for `[-4, -4, -5]`.

### `powerset`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host/baseline__powerset__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host/rag__powerset__attempt2.json`

Code difference:
- Baseline returned `[[first] + subset for subset in rest_subsets] + rest_subsets`.
- RAG returned `rest_subsets + [[first] + subset for subset in rest_subsets]`, which matches the expected order in the test.

Prompt difference:
- Baseline prompt only contained the buggy code and failure signal.
- RAG attempt 2 included retrieved examples plus the follow-up assertion diff showing the ordering mismatch at index `0`.

### `reverse_linked_list`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_host/baseline__reverse_linked_list__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_host/rag__reverse_linked_list__attempt1.json`

Code difference:
- Baseline drifted to `node.next`, which is incompatible with QuixBugs' `Node.successor`.
- RAG preserved `node.successor` and passed.

Prompt difference:
- Baseline prompt only contained the buggy code and failure signal.
- RAG prompt included retrieved bug-fix examples and repair lessons, which appears to have reduced schema drift toward the common `next` naming convention.

## Practical takeaway

In this traced run, the most useful RAG effects were:
- reducing naming/schema drift (`reverse_linked_list`)
- using second-attempt failure feedback to fix edge-case behavior (`max_sublist_sum`)
- using second-attempt failure feedback to fix output ordering (`powerset`)

The traced JSON files now contain the exact prompt/messages, generated code, and pytest output for each attempt, so future comparisons can be made directly from the artifacts instead of reconstructing prompts after the run.
