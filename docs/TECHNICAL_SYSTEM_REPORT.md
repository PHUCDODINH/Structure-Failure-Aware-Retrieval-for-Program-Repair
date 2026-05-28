# Technical Report: Bug-Fix RAG Evaluation System

Date: 2026-03-12  
Project root: `/Users/dodinhphuc/PycharmProjects/RAGtest`

## 1. Purpose

This repository implements a retrieval-augmented code generation and code repair evaluation system.

The core research question is:

> Can retrieval of external bug-fix examples improve LLM performance on code generation and code repair tasks?

The system currently evaluates that question on:

- HumanEval
- MBPP
- QuixBugs

The current framework supports two modes:

- `baseline`: no retrieval
- `rag`: retrieve external bug-fix examples and inject them into the prompt

The main current retrieval corpus is an external Python bug-fix corpus derived from BugsInPy and filtered into benchmark-specific retrieval profiles.

## 2. Current System Scope

There are really two related systems in this repo:

1. A generation system for HumanEval and MBPP
2. A repair system for QuixBugs

They share the same retrieval backbone:

- external bug-fix JSONL corpus
- dense embedding index
- FAISS nearest-neighbor search
- metadata-aware reranking

But they differ in:

- query text
- prompt structure
- evaluation harness
- whether test-failure feedback is used

## 3. Repository Components

### 3.1 Generation Models

- Baseline generation: [humaneval_generator_baseline.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/humaneval_generator_baseline.py)
- RAG generation: [humaneval_generator_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/humaneval_generator_rag.py)

These wrappers are used for both HumanEval and MBPP.

### 3.2 Repair Models

- Baseline repair: [repair_baseline.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/repair_baseline.py)
- RAG repair: [repair_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/repair_rag.py)

These wrappers are used by QuixBugs and PyBugHive-style repair evaluation.

### 3.3 Evaluation Harnesses

- HumanEval: [eval_humaneval.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/eval_humaneval.py)
- MBPP: [eval_mbpp.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/eval_mbpp.py)
- QuixBugs: [evaluate_quixbugs.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/evaluate_quixbugs.py)
- PyBugHive integration: [evaluate_pybughive.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/evaluate_pybughive.py)

### 3.4 Retrieval / Indexing

- Index builder: [build_index.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/retrieval/build_index.py)
- Index loading / embedding: [index_store.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/retrieval/index_store.py)

### 3.5 Corpus / Dataset Documentation

- Corpus specification: [BUGFIX_CORPUS_SPEC.md](/Users/dodinhphuc/PycharmProjects/RAGtest/docs/BUGFIX_CORPUS_SPEC.md)
- External corpus workflow: [EXTERNAL_CORPUS_WORKFLOW.md](/Users/dodinhphuc/PycharmProjects/RAGtest/docs/EXTERNAL_CORPUS_WORKFLOW.md)

## 4. Retrieval Corpus

### 4.1 Original Situation

Earlier in the project, the retrieval corpus was built by merging:

- QuixBugs bug-fix pairs
- synthetic MBPP bug-fix pairs

That created leakage for MBPP and QuixBugs because evaluation tasks overlapped with retrieval content.

### 4.2 Current Corpus

The current active external corpus is BugsInPy-derived:

- normalized external source: [bugsinpy_normalized.jsonl](/Users/dodinhphuc/PycharmProjects/RAGtest/data/external_sources/bugsinpy_normalized.jsonl)
- record count: `645`

After filtering:

- repair corpus: [repair_external_bugfix.jsonl](/Users/dodinhphuc/PycharmProjects/RAGtest/data/corpora/repair_external_bugfix.jsonl)
- retained entries: `551`

Current repair index metadata:

- index info: [info.txt](/Users/dodinhphuc/PycharmProjects/RAGtest/data/indexes/repair_clean/info.txt)
- embedding model: `all-MiniLM-L6-v2`
- entries indexed: `551`
- vector dimension: `384`

### 4.3 Benchmark Profiles

Current index profiles are resolved in [index_store.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/retrieval/index_store.py):

- `legacy`
- `external`
- `humaneval_clean`
- `mbpp_clean`
- `quixbugs_clean`
- `repair_clean`

Important note:

At the moment, these clean profiles are mostly fed from the same BugsInPy-derived source because BugsInPy is the only fully built external corpus in active use. That means profile separation exists in code, but corpus diversity is still limited.

## 5. Retrieval Logic

### 5.1 Embeddings

The retrieval system uses:

- `sentence-transformers/all-MiniLM-L6-v2`
- loaded via [index_store.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/retrieval/index_store.py)
- embeddings are computed with `SentenceTransformer.encode(...)`

### 5.2 What Gets Embedded

Index construction in [build_index.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/retrieval/build_index.py) embeds:

- `buggy_code` if present
- otherwise `code`

So retrieval similarity is computed over buggy code, not fixed code.

### 5.3 FAISS Search

The system builds a dense FAISS index:

- index type: `faiss.IndexFlatL2`

At query time:

1. embed query text
2. search dense nearest neighbors
3. retrieve a candidate pool
4. rerank candidates
5. keep top `k`

### 5.4 Query Types by Task

Generation tasks:

- Query is the task prompt text
- Implemented in [humaneval_generator_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/humaneval_generator_rag.py)

Repair tasks:

- Query is the current buggy code
- Implemented in [repair_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/repair_rag.py)

### 5.5 Reranking

The reranker is a heuristic scorer layered on top of dense retrieval.

Generation reranking in [humaneval_generator_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/humaneval_generator_rag.py) uses:

- identifier overlap
- candidate scope bonus
- file count bonus
- candidate patch size penalty
- query/code length similarity
- framework-heavy penalty

Repair reranking in [repair_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/repair_rag.py) uses:

- identifier overlap
- candidate scope bonus
- files-changed bonus
- patch-size penalty
- code-length similarity
- dense-rank bonus

### 5.6 Context Size

Both generators and repairers use:

- diff-focused snippets instead of whole files
- a maximum of `2` retrieved examples
- a total context cap

This was necessary because whole-file BugsInPy examples caused prompt-size and TPM problems for smaller models.

## 6. Prompting Design

## 6.1 Generation Baseline Prompt

Baseline generation in [humaneval_generator_baseline.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/humaneval_generator_baseline.py) uses:

- a system instruction telling the model to output runnable Python only
- the benchmark task prompt as the user message

HumanEval baseline prompt structure:

```text
System:
You are an expert Python programmer.
Write ONLY runnable Python code.
NO comments, NO explanations, NO markdown.
Output ONLY the function implementation.

User:
<benchmark prompt>
```

MBPP baseline is stricter. It builds an explicit `solution(...)` contract and behavior examples in [eval_mbpp.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/eval_mbpp.py).

## 6.2 Generation RAG Prompt

Generation RAG in [humaneval_generator_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/humaneval_generator_rag.py) injects compact bug-fix examples before the task:

```text
You are an expert Python programmer.
Your task is to write a Python function that solves the described problem.
Return ONLY the code, starting with the function definition.
NO markdown, NO comments outside the code, NO explanations.

Here are compact examples of similar bugs and their fixes.
Focus on the transfer lesson and correction pattern, not the project-specific details.

--- Example 1 (source) ---
[Transfer Lesson]:
<heuristic lesson>

[Buggy Snippet]:
<diff-focused buggy code>

[Fixed Snippet]:
<diff-focused fixed code>

--- Example 2 (source) ---
...

Now, solve the following problem correctly:
Problem:
<task prompt>

Solution:
```

The generation-side lesson is produced by `_infer_generation_lesson(...)` in [humaneval_generator_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/humaneval_generator_rag.py).

## 6.3 Repair Baseline Prompt

Baseline repair in [repair_baseline.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/repair_baseline.py) uses:

```text
System:
You are an expert Python engineer. Your task is to FIX the following buggy Python code.
STRICT RULES:
1. Output ONLY corrected Python code.
2. NO explanation, NO comments, NO markdown.
3. Preserve the same function name.
4. Ensure the code is runnable.

User:
Buggy code:
<buggy code>

Optional description:
<failure signal>

Please provide the FIXED code:
```

## 6.4 Repair RAG Prompt

Repair RAG in [repair_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/repair_rag.py) uses:

```text
You are an expert Python engineer.
Your task is to FIX the following buggy Python code.
STRICT RULES:
1. Output ONLY corrected Python code.
2. NO explanation, NO comments, NO markdown.
3. Preserve the same function name.
4. Ensure runnable, correct Python.

Below are compact buggy-to-fixed examples. Focus on the correction pattern.

# Repair lesson:
<heuristic lesson>

# Buggy snippet:
<diff-focused buggy snippet>

# Fixed snippet:
<diff-focused fixed snippet>

# Repair lesson:
...

# Now fix this code:
<buggy code>

Description (optional): <failure signal>

# Your FIXED code:
```

## 7. How `repair_lesson` Is Created

The `repair_lesson` is not stored in the dataset.

It is generated dynamically at runtime by `_infer_repair_lesson(...)` in [repair_rag.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/models/repair_rag.py).

The process is:

1. Build a diff-focused buggy snippet and fixed snippet
2. Inspect the changed text heuristically
3. Select one or two lesson sentences from a predefined template set
4. Deduplicate and inject them into the prompt

Current lesson triggers include:

- object attribute changes
- return expression changes
- boolean/guard tightening
- precondition validation
- boundary/off-by-one cues
- collection / pointer-style updates
- arithmetic / accumulator updates

Example possible lesson outputs:

- `Use the correct object attributes and preserve the local data model.`
- `Handle edge cases explicitly in the returned value.`
- `Preserve the required output ordering when combining partial results.`
- `Fix boundary and off-by-one handling around the changed logic.`
- `Check collection updates and pointer-style state transitions carefully.`

This was recently improved because the earlier heuristic over-produced the same generic sentence for many tasks.

## 8. Evaluation Harness Design

## 8.1 HumanEval

HumanEval evaluation in [eval_humaneval.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/eval_humaneval.py):

- loads prompt, entry point, and `check(candidate)` test code
- prepends a typing/import preamble
- imports generated candidate code as a module
- executes `check(candidate_fn)`
- checkpoints results task-by-task

## 8.2 MBPP

MBPP evaluation in [eval_mbpp.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/eval_mbpp.py):

- parses test assertions
- infers callable arity and target behavior examples
- forces output function name `solution`
- reconstructs `Pair(a,b)` style inputs when needed
- executes tests with a timeout
- checkpoints per task

This harness changed substantially during the work. Earlier MBPP numbers are not directly comparable to newer ones because the evaluation contract was corrected.

## 8.3 QuixBugs

QuixBugs evaluation in [evaluate_quixbugs.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/evaluate_quixbugs.py):

- autodetects buggy problems with matching tests
- copies repaired code into a temporary QuixBugs package layout
- runs pytest on the target problem
- captures failure summaries
- for RAG, allows up to 2 attempts
- retries the second attempt with new failing-test feedback
- supports per-attempt trace logging
- checkpoints completed problems
- avoids recording infrastructure failures as false benchmark misses

This is currently the most mature harness in the project.

## 9. Tracing and Debugging

QuixBugs tracing is implemented in [evaluate_quixbugs.py](/Users/dodinhphuc/PycharmProjects/RAGtest/src/eval/evaluate_quixbugs.py).

When `--trace-dir` is enabled, each attempt writes a JSON file containing:

- problem name
- model
- input buggy code
- failure signal
- generated code
- pass/fail result
- stdout/stderr from pytest
- baseline messages or RAG prompt
- retrieved examples for RAG

This made it possible to inspect exact prompt/code differences between baseline and RAG.

## 10. Baseline vs RAG Example

The clearest example is `reverse_linked_list` from the traced `gpt-4.1` QuixBugs run.

### 10.1 Baseline Prompt

Source trace: [baseline__reverse_linked_list__attempt1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/traces/quixbugs_40_baseline_gpt41_v1/baseline__reverse_linked_list__attempt1.json)

```text
System:
You are an expert Python engineer. Your task is to FIX the following buggy Python code.
STRICT RULES:
1. Output ONLY corrected Python code.
2. NO explanation, NO comments, NO markdown.
3. Preserve the same function name.
4. Ensure the code is runnable.

User:
Buggy code:
def reverse_linked_list(node):
    prevnode = None
    while node:
        nextnode = node.successor
        node.successor = prevnode
        prevnode = node
        node = nextnode
    return prevnode

Optional description:
Original buggy code unexpectedly passed the available tests.

Please provide the FIXED code:
```

### 10.2 RAG Prompt

Source trace: [rag__reverse_linked_list__attempt1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/traces/quixbugs_40_rag_gpt41_v1/rag__reverse_linked_list__attempt1.json)

```text
You are an expert Python engineer.
Your task is to FIX the following buggy Python code.
STRICT RULES:
1. Output ONLY corrected Python code.
2. NO explanation, NO comments, NO markdown.
3. Preserve the same function name.
4. Ensure runnable, correct Python.

Below are compact buggy-to-fixed examples. Focus on the correction pattern.

# Repair lesson:
Check collection updates and pointer-style state transitions carefully.

# Buggy snippet:
<retrieved buggy snippet>

# Fixed snippet:
<retrieved fixed snippet>

# Repair lesson:
Tighten boolean guard conditions instead of relying on broad matches. Check collection updates and pointer-style state transitions carefully.

# Buggy snippet:
<retrieved buggy snippet>

# Fixed snippet:
<retrieved fixed snippet>

# Now fix this code:
def reverse_linked_list(node):
    prevnode = None
    while node:
        nextnode = node.successor
        node.successor = prevnode
        prevnode = node
        node = nextnode
    return prevnode

Description (optional): Original buggy code unexpectedly passed the available tests.

# Your FIXED code:
```

### 10.3 Generated Code Difference

Baseline output:

```python
def reverse_linked_list(node):
    prevnode = None
    while node:
        nextnode = node.next
        node.next = prevnode
        prevnode = node
        node = nextnode
    return prevnode
```

RAG output:

```python
def reverse_linked_list(node):
    prevnode = None
    while node:
        nextnode = node.successor
        node.successor = prevnode
        prevnode = node
        node = nextnode
    return prevnode
```

Interpretation:

- baseline drifted toward the generic linked-list attribute `next`
- RAG preserved the local schema `successor`
- the retrieval examples and repair lessons appear to reduce schema drift

## 11. Second Concrete Example

Problem: `wrap`

Baseline trace:

- [baseline__wrap__attempt1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/traces/quixbugs_40_baseline_gpt41_v1/baseline__wrap__attempt1.json)

RAG trace:

- [rag__wrap__attempt2.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/traces/quixbugs_40_rag_gpt41_v1/rag__wrap__attempt2.json)

Baseline output:

```python
def wrap(text, cols):
    lines = []
    while len(text) > cols:
        end = text.rfind(' ', 0, cols)
        if end == -1:
            end = cols
        line, text = text[:end].rstrip(), text[end:].lstrip()
        lines.append(line)
    if text:
        lines.append(text)
    return lines
```

RAG output:

```python
def wrap(text, cols):
    lines = []
    while len(text) > cols:
        end = text.rfind(' ', 0, cols + 1)
        if end == -1:
            end = cols
        line, text = text[:end], text[end:]
        lines.append(line)
    if text:
        lines.append(text)
    return lines
```

Interpretation:

- baseline normalized whitespace too aggressively
- RAG used failure feedback plus retrieved examples to preserve the benchmark's expected output contract

## 12. Recorded Results

## 12.1 Refreshed Generation Results (`gpt-4o`)

HumanEval:

- baseline: `137/164` in [humaneval_baseline_gpt4o_host_full.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/humaneval_baseline_gpt4o_host_full.json)
- RAG: `138/164` in [humaneval_rag_gpt4o_host_full.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/humaneval_rag_gpt4o_host_full.json)
- delta: `+1`

MBPP:

- baseline: `86/100` in [mbpp_baseline_gpt4o_host_100.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/mbpp_baseline_gpt4o_host_100.json)
- RAG: `88/100` in [mbpp_rag_gpt4o_host_100.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/mbpp_rag_gpt4o_host_100.json)
- delta: `+2`

## 12.2 QuixBugs Results by Model

### `gpt-4o-mini`

- baseline: `31/40` in [quixbugs_baseline_gpt4omini_external_40_trace1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/quixbugs_baseline_gpt4omini_external_40_trace1.json)
- RAG: `34/40` in [quixbugs_rag_gpt4omini_external_40_trace1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/quixbugs_rag_gpt4omini_external_40_trace1.json)
- delta: `+3`

RAG-only wins:

- `depth_first_search`
- `lcs_length`
- `max_sublist_sum`
- `quicksort`
- `rpn_eval`

Baseline-only wins:

- `lis`
- `shortest_paths`

### `gpt-4o`

- baseline: `32/40` in [quixbugs_baseline_gpt4o_external_40_trace3.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/quixbugs_baseline_gpt4o_external_40_trace3.json)
- RAG: `36/40` in [quixbugs_rag_gpt4o_external_40_trace3.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/quixbugs_rag_gpt4o_external_40_trace3.json)
- delta: `+4`

RAG-only wins:

- `find_first_in_sorted`
- `max_sublist_sum`
- `powerset`
- `reverse_linked_list`
- `shortest_path_length`

Baseline-only wins:

- `topological_ordering`

Reference analysis:

- [QUIXBUGS_TRACE_ANALYSIS_V3.md](/Users/dodinhphuc/PycharmProjects/RAGtest/docs/QUIXBUGS_TRACE_ANALYSIS_V3.md)

### `gpt-4.1`

- baseline: `31/40` in [quixbugs_baseline_gpt41_external_40_trace1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/quixbugs_baseline_gpt41_external_40_trace1.json)
- RAG: `39/40` in [quixbugs_rag_gpt41_external_40_trace1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/quixbugs_rag_gpt41_external_40_trace1.json)
- delta: `+8`

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

Reference analysis:

- [QUIXBUGS_TRACE_ANALYSIS_GPT41.md](/Users/dodinhphuc/PycharmProjects/RAGtest/docs/QUIXBUGS_TRACE_ANALYSIS_GPT41.md)

## 12.3 Summary Table

| Benchmark | Model | Baseline | RAG | Delta |
| --- | --- | ---: | ---: | ---: |
| HumanEval | `gpt-4o` | 137/164 | 138/164 | +1 |
| MBPP | `gpt-4o` | 86/100 | 88/100 | +2 |
| QuixBugs | `gpt-4o-mini` | 31/40 | 34/40 | +3 |
| QuixBugs | `gpt-4o` | 32/40 | 36/40 | +4 |
| QuixBugs | `gpt-4.1` | 31/40 | 39/40 | +8 |

## 13. Interpretation

### 13.1 What the Results Support

The current results support the following claims:

- The repaired and cleaned RAG framework is now consistently positive on all three active benchmarks.
- The effect is modest on generation benchmarks.
- The effect is clearly stronger on code repair, especially QuixBugs.
- Stronger models extract more value from the same repair-oriented retrieval context.

### 13.2 What the Results Do Not Support

The results do not support:

- a claim that RAG gives large universal gains on code generation
- a claim that all earlier results in the project were already valid
- a claim that the retrieval corpus is fully optimal or benchmark-aligned

## 14. Limitations and Caveats

### 14.1 Earlier Leakage

Earlier MBPP and QuixBugs retrieval experiments used benchmark-derived content and are not the right basis for final claims.

### 14.2 Current Corpus Concentration

The current clean indexes are mostly BugsInPy-derived, so retrieval diversity is still limited.

### 14.3 QuixBugs Source Contamination

Some local QuixBugs buggy files contain embedded triple-quoted candidate fixes in the source file itself. This means the prompt may include extra answer-like material that is not part of a clean buggy-only formulation.

This is visible in traced prompts such as:

- [baseline__reverse_linked_list__attempt1.json](/Users/dodinhphuc/PycharmProjects/RAGtest/experiments/traces/quixbugs_40_baseline_gpt41_v1/baseline__reverse_linked_list__attempt1.json)

This should be cleaned if the benchmark is to be treated as a fully rigorous repair setup.

### 14.4 MBPP Comparability

MBPP numbers changed significantly after:

- fixing prompt contract generation
- enforcing `solution(...)`
- parsing visible behavior examples
- adding test timeouts

So old MBPP totals and new MBPP totals are not directly comparable.

### 14.5 Variance

QuixBugs showed run-to-run variance before the latest traced setup stabilized. The current traces are much more trustworthy, but repeated trials would still strengthen the research story.

## 15. Why the Current RAG Setup Appears to Help

Based on the traces, the current gains are most likely coming from four behaviors:

- reduced schema drift
- better edge-case handling
- better return-contract matching
- stronger recovery on retry after failing-test feedback

The system is not merely retrieving similar code. The strongest current behavior is:

- retrieve bug-fix examples
- summarize them into a small repair lesson
- inject compact bug/fix context
- test the repair
- retry with failure feedback when needed

That is why the QuixBugs gains are larger than the HumanEval / MBPP gains.

## 16. Recommended Research Framing

The most defensible framing is:

> A bug-fix RAG system using an external Python bug-fix corpus yields small positive transfer gains on code generation benchmarks and substantially larger gains on a code repair benchmark, with the strongest improvements appearing when failure-aware iterative repair is used.

The strongest evidence in the current project is QuixBugs:

- `gpt-4o-mini`: `+3`
- `gpt-4o`: `+4`
- `gpt-4.1`: `+8`

The most cautious wording for the full project is:

- RAG appears modestly helpful for generation
- RAG is most effective for repair
- better models benefit more from this retrieval design

## 17. Next Technical Steps

Recommended next steps:

- clean the contaminated QuixBugs source files used in prompts
- run repeated trials for QuixBugs and report mean / variance
- add a second external corpus such as PyBugHive once retrieval/eval leakage is controlled
- build a more generation-aligned bug-fix corpus for HumanEval and MBPP
- add a provider abstraction if cross-provider testing such as Gemini is required

## 18. Bottom Line

The current system is no longer just a generic dense-retrieval wrapper around an LLM.

It is now a structured bug-fix RAG framework with:

- benchmark-specific retrieval profiles
- diff-focused bug/fix examples
- heuristic repair and transfer lessons
- metadata-aware reranking
- corrected evaluation harnesses
- checkpointing and tracing
- and an iterative repair loop for QuixBugs

The strongest conclusion from the present evidence is:

> The framework works best as a code-repair RAG system, and QuixBugs currently provides the clearest evidence that the bug-fix retrieval design is helping.
