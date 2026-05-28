# QuixBugs Trace Analysis (`gpt-4.1`)

Model: `gpt-4.1`

Artifacts from the traced full `40/40` rerun:
- Baseline results: `experiments/quixbugs_baseline_gpt41_external_40_trace1.json`
- RAG results: `experiments/quixbugs_rag_gpt41_external_40_trace1.json`
- Baseline traces: `experiments/traces/quixbugs_40_baseline_gpt41_v1/`
- RAG traces: `experiments/traces/quixbugs_40_rag_gpt41_v1/`

Run summary:
- Baseline: `31/40`
- RAG: `39/40`
- Delta: `+8` for RAG

This is the strongest QuixBugs repair result in the project so far. On this run, RAG recovered eight problems that baseline missed, and baseline had no exclusive wins.

## Swap summary

RAG-only wins:
- `kheapsort`
- `lcs_length`
- `max_sublist_sum`
- `powerset`
- `reverse_linked_list`
- `shortest_path_length`
- `topological_ordering`
- `wrap`

Baseline-only wins:
- none

## Key recovered repairs

### `reverse_linked_list`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_gpt41_v1/baseline__reverse_linked_list__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_gpt41_v1/rag__reverse_linked_list__attempt1.json`

Observed difference:
- Baseline drifted to the generic linked-list field `next` and failed with `AttributeError`.
- RAG preserved QuixBugs' actual field name `successor` and passed immediately.

Why it matters:
- this is the clearest schema-preservation example,
- and it matches the intended role of retrieved bug-fix examples plus the new attribute-aware repair lessons.

### `wrap`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_gpt41_v1/baseline__wrap__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_gpt41_v1/rag__wrap__attempt2.json`

Observed difference:
- Baseline stripped leading/trailing spaces and wrapped too aggressively, so the output lines no longer matched the benchmark contract.
- RAG used the retry plus failure feedback to preserve the expected splitting behavior and passed on attempt 2.

Why it matters:
- this is a good example of RAG helping with benchmark-specific output contracts rather than only raw algorithm fixes.

### `kheapsort`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_gpt41_v1/baseline__kheapsort__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_gpt41_v1/rag__kheapsort__attempt2.json`

Observed difference:
- Baseline returned nothing for the `k <= 0` case.
- RAG repaired the edge-case behavior on retry and yielded the expected items.

Why it matters:
- it shows the current repair loop is helping on control-flow and edge-case corrections, not only naming issues.

### `topological_ordering`
- Baseline trace: `experiments/traces/quixbugs_40_baseline_gpt41_v1/baseline__topological_ordering__attempt1.json`
- RAG trace: `experiments/traces/quixbugs_40_rag_gpt41_v1/rag__topological_ordering__attempt1.json`

Observed difference:
- Baseline produced an order that violated the exact expected sequence.
- RAG generated a passing ordering in one shot.

Why it matters:
- earlier `gpt-4o` traced runs sometimes had this as a baseline-only win,
- so `gpt-4.1` + the current RAG setup is materially stronger on this ordering-sensitive case.

## Practical takeaway

The current QuixBugs repair setup is no longer just showing a weak positive trend. On `gpt-4.1`, it produces a large and clean improvement:
- `39/40` vs `31/40`
- no baseline-only wins
- gains spread across edge cases, return-contract fixes, schema preservation, and ordering-sensitive repairs

The remaining miss is `subsequences`, which means the system is close to saturating this benchmark with `gpt-4.1` under the current prompt and retrieval design.

For research purposes, this is the strongest evidence in the repo that the bug-fix RAG framework is working for code repair rather than only appearing neutral or slightly positive.
