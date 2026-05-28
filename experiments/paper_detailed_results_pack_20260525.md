# Paper Detailed Results Pack

Generated: 2026-05-25

## 1. Main Result Interpretation

The paper should frame the contribution as structured failure-aware retrieval, not as a universally stronger repair system. The strongest evidence is retrieval relevance plus controlled QuixBugs gains. PyBugHive and HumanEvalFix are important because they show the limits: retrieval relevance does not automatically convert into better patches, especially for large files or already-strong direct baselines.

## 2. Retrieval-Only Evidence

Source file: `experiments/paper_retrieval_relevance_quixbugs_pybughive_v3.json`.

| Benchmark | Variant | Top-1 Tag | Top-2 Tag | Top-5 Tag | Top-1 Scope | Top-1 Symbol |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| quixbugs | code_only | 0.272 | 0.237 | 0.218 | 0.100 | 0.017 |
| quixbugs | raw_text | 0.228 | 0.232 | 0.221 | 0.075 | 0.019 |
| quixbugs | raw_text_rerank | 0.247 | 0.221 | 0.195 | 0.100 | 0.016 |
| quixbugs | structured | 0.315 | 0.378 | 0.394 | 0.100 | 0.020 |
| pybughive_black | code_only | 0.166 | 0.158 | 0.123 | 0.529 | 0.063 |
| pybughive_black | raw_text | 0.166 | 0.158 | 0.123 | 0.529 | 0.063 |
| pybughive_black | raw_text_rerank | 0.147 | 0.120 | 0.114 | 0.529 | 0.063 |
| pybughive_black | structured | 0.166 | 0.181 | 0.258 | 0.529 | 0.063 |

Paper takeaway: structured reranking gives the clearest gain on QuixBugs top-2/top-5 repair-pattern compatibility, and improves PyBugHive top-5 tag compatibility. The mechanism is strongest at improving the candidate pool, not necessarily top-1 repair success.

## 3. QuixBugs Primary Downstream Results

Setting: single attempt, single candidate, `k=2`.

### gpt-4o
| Variant | Pass | Total | Pass Rate |
| --- | ---: | ---: | ---: |
| baseline | 35 | 40 | 87.5% |
| code_only | 37 | 40 | 92.5% |
| raw_text | 35 | 40 | 87.5% |
| raw_text_rerank | 34 | 40 | 85.0% |
| structured | 37 | 40 | 92.5% |

### gpt-4.1
| Variant | Pass | Total | Pass Rate |
| --- | ---: | ---: | ---: |
| baseline | 36 | 40 | 90.0% |
| code_only | 35 | 40 | 87.5% |
| raw_text | 34 | 40 | 85.0% |
| raw_text_rerank | 36 | 40 | 90.0% |
| structured | 35 | 40 | 87.5% |

### gpt-4o-mini
| Variant | Pass | Total | Pass Rate |
| --- | ---: | ---: | ---: |
| baseline | 33 | 40 | 82.5% |
| code_only | 33 | 40 | 82.5% |
| raw_text | 31 | 40 | 77.5% |
| raw_text_rerank | 32 | 40 | 80.0% |
| structured | 30 | 40 | 75.0% |

Paper takeaway: structured RAG helps on `gpt-4o`, ties code-only there, but is not model-universal. This should be discussed as model sensitivity rather than hidden as noise.

## 4. QuixBugs Structured Field Ablation

Source file: `experiments/paper_fieldablation_quixbugs_gpt4o_v2_summary.json`.

| Condition | Pass | Total | Pass Rate | Delta vs Full |
| --- | ---: | ---: | ---: | ---: |
| full | 37 | 40 | 92.5% | 0 |
| no_contract_tags | 36 | 40 | 90.0% | -1 |
| no_suspicious_symbols | 36 | 40 | 90.0% | -1 |
| no_failure_mode | 36 | 40 | 90.0% | -1 |
| no_exception_type | 37 | 40 | 92.5% | 0 |
| no_test_name | 36 | 40 | 90.0% | -1 |
| no_assertion_summary | 36 | 40 | 90.0% | -1 |

Paper takeaway: contract tags, suspicious symbols, and failure mode each contribute a small but measurable downstream signal. Exception type does not matter on QuixBugs.

## 5. QuixBugs Variance

| Variant | Pass Counts | Mean | Std | Min | Max |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 37, 35, 36, 36, 35 | 89.5% | 2.09% | 87.5% | 92.5% |
| code_only | 36, 36, 37, 36, 36 | 90.5% | 1.12% | 90.0% | 92.5% |
| raw_text | 37, 36, 37, 37, 35 | 91.0% | 2.24% | 87.5% | 92.5% |
| raw_text_rerank | 35, 35, 35, 36, 35 | 88.0% | 1.12% | 87.5% | 90.0% |
| structured | 37, 35, 36, 37, 37 | 91.0% | 2.24% | 87.5% | 92.5% |

Paper takeaway: structured and raw-text tie in mean pass rate across repeated trials, while structured remains strong on retrieval relevance. Use this to keep claims honest.

## 6. PyBugHive-Black Realistic-Repo Results

### Original Black Setting
| Variant | Pass | Total | Pass Rate |
| --- | ---: | ---: | ---: |
| baseline | 23 | 34 | 67.6% |
| code_only | 12 | 34 | 35.3% |
| raw_text | 11 | 34 | 32.4% |
| raw_text_rerank | 11 | 34 | 32.4% |
| structured | 11 | 34 | 32.4% |

### Project-Held-Out Black Setting
Held-out profile: `repair_clean_holdout_pybughive_projects`. This removes same-project BugsInPy examples from retrieval. Verified remaining excluded-project records: 0.

| Variant | Pass | Total | Pass Rate |
| --- | ---: | ---: | ---: |
| baseline | 23 | 34 | 67.6% |
| code_only | 23 | 34 | 67.6% |
| raw_text | not run | 34 | - |
| raw_text_rerank | 12 | 34 | 35.3% |
| structured | 23 | 34 | 67.6% |

Failure profile in held-out Black: code-only and structured both had 7 patch rejections and 4 applied-test failures; raw-text-rerank had 16 patch rejections and 6 test failures.

Paper takeaway: project holdout reduces contamination concern. Structured RAG remains competitive with baseline/code-only in this held-out setting, but does not improve over them. The large-file patch layer is still a bottleneck.

## 7. Patch-Layer Experiments on PyBugHive

| Patch Setting | Pass | Total | Pass Rate | Note |
| --- | ---: | ---: | ---: | ---: |
| structured original | 11 | 34 | 32.4% | pre strict-line-range primary |
| strict line-range | 9 | 34 | 26.5% | strict JSON span contract |
| strict + validation retry | 11 | 34 | 32.4% | one rejected-patch retry |
| strict + retry + verifier feedback | 12 | 34 | 35.3% | two repair attempts, failure-localized snippets |

Paper takeaway: stricter patching improves trace quality and prevents silent fuzzy application, but does not by itself improve repair success. Verifier-feedback localization recovers a small gain to 12/34.

## 8. HumanEvalFix Results

Dataset: BigCode/OctoPack HumanEvalPack Python repair split, 164 tasks. Prompt mode: tests. Retrieval DB: BugsInPy-only `repair_clean`; HumanEval contamination check found 0 matching records/mentions.

| Model | Baseline | Baseline Rate | Structured RAG | Structured Rate | Delta | RAG-only Wins | Baseline-only Wins | Both Fail |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-4o | 132/164 | 80.5% | 126/164 | 76.8% | -6 | 2 | 8 | 30 |
| gpt-4.1 | 131/164 | 79.9% | 129/164 | 78.7% | -2 | 3 | 5 | 30 |
| gpt-4o-mini | 112/164 | 68.3% | 109/164 | 66.5% | -3 | 7 | 10 | 45 |

### HumanEvalFix by Bug Type, gpt-4o
| Bug Type | Baseline | Baseline Rate | Structured RAG | Structured Rate | Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| excess logic | 26/31 | 83.9% | 23/31 | 74.2% | -3 |
| function misuse | 5/8 | 62.5% | 5/8 | 62.5% | 0 |
| missing logic | 22/33 | 66.7% | 22/33 | 66.7% | 0 |
| operator misuse | 20/25 | 80.0% | 19/25 | 76.0% | -1 |
| value misuse | 41/44 | 93.2% | 40/44 | 90.9% | -1 |
| variable misuse | 18/23 | 78.3% | 17/23 | 73.9% | -1 |

Paper takeaway: HumanEvalFix is clean and useful as appendix/robustness evidence, but it does not support the structured-RAG success claim. RAG slightly hurts across all tested models.

## 9. Pairwise Win/Loss Examples

### HumanEvalFix gpt-4o
- RAG-only wins: ['Python/132', 'Python/93']
- Baseline-only wins: ['Python/113', 'Python/116', 'Python/118', 'Python/33', 'Python/36', 'Python/46', 'Python/63', 'Python/83']
- Both fail count: 30

### HumanEvalFix gpt-4.1
- RAG-only wins: ['Python/125', 'Python/49', 'Python/75']
- Baseline-only wins: ['Python/134', 'Python/151', 'Python/52', 'Python/87', 'Python/93']
- Both fail count: 30

### HumanEvalFix gpt-4o-mini
- RAG-only wins: ['Python/132', 'Python/143', 'Python/163', 'Python/30', 'Python/70', 'Python/80', 'Python/90']
- Baseline-only wins: ['Python/1', 'Python/10', 'Python/102', 'Python/105', 'Python/114', 'Python/140', 'Python/153', 'Python/19', 'Python/51', 'Python/96']
- Both fail count: 45

## 10. Prompt and Solution Illustration

Example: HumanEvalFix `Python/132`, `gpt-4o`. Baseline failed; structured RAG passed.

Trace files:
- `experiments/traces/humanevalfix_baseline_gpt4o_full_v1/baseline__Python_132.json`
- `experiments/traces/humanevalfix_structured_gpt4o_full_v1/rag__Python_132.json`

### Buggy Code
```python
def is_nested(string):
    opening_bracket_index = []
    closing_bracket_index = []
    for i in range(len(string)):
        if string[i] == '(':
            opening_bracket_index.append(i)
        else:
            closing_bracket_index.append(i)
    closing_bracket_index.reverse()
    cnt = 0
    i = 0
    l = len(closing_bracket_index)
    for idx in opening_bracket_index:
        if i < l and idx < closing_bracket_index[i]:
            cnt += 1
            i += 1
    return cnt >= 2
```

### Baseline Prompt Shape
```text
Buggy code:
def is_nested(string):
    opening_bracket_index = []
    closing_bracket_index = []
    for i in range(len(string)):
        if string[i] == '(':
            opening_bracket_index.append(i)
        else:
            closing_bracket_index.append(i)
    closing_bracket_index.reverse()
    cnt = 0
    i = 0
    l = len(closing_bracket_index)
    for idx in opening_bracket_index:
        if i < l and idx < closing_bracket_index[i]:
            cnt += 1
            i += 1
    return cnt >= 2

    


Optional description:
Task id: Python/132

Entry point: is_nested

Bug type: value misuse

Failure symptoms: incorrect output

Tests:
def check(is_nested):

    # Check some simple cases
    assert is_nested('[[]]') == True, "This prints if this assert fails 1 (good for debugging!)"
    assert is_nested('[]]]]]]][[[[[]') == False
    assert is_nested('[][]') == False
    assert is_nested(('[]')) == False
    assert is_nested('[[[[]]]]') == True
    assert is_nested('[]]]]]]]]]]') == False
    assert is_nested('[][][[]]') == True
...
```

### Structured RAG Prompt Additions
The RAG prompt includes the same buggy code and tests, plus retrieved examples and repair lessons before the target bug.

Example 1: `bugsinpy:black:13:blib2to3:pgen2:tokenize.py`
- Repair lesson: Tighten boolean guard conditions instead of relying on broad matches. Check collection updates and pointer-style state transitions carefully.
Example 2: `bugsinpy:pandas:14:pandas:tests:arithmetic:conftest.py`
- Repair lesson: Use the correct object attributes and preserve the local data model. Handle edge cases explicitly in the returned value.

Prompt excerpt:
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
Tighten boolean guard conditions instead of relying on broad matches. Check collection updates and pointer-style state transitions carefully.

# Buggy snippet:
tok = (NAME, token, spos, epos, line)
                    if token == 'async' and not stashed:
                        stashed = tok
                        continue

                    if token == 'def':
                        if (stashed
                                and stashed[0] == NAME
                                and stashed[1] == 'async'):

                            async_def = True
                            async_def_indent = indents[-1]
...
if token == 'def':
                        if (stashed
                                and stashed[0] == NAME
                                and stashed[1] == 'async'):

                            async_def = True
                            async_def_indent = indents[-1]

                            yield (ASYNC, stashed[1],
                                   stashed[2], stashed[3],
                                   stashed[4])
                            stashed = None

# Fixed snippet:
tok = (NAME, token, spos, epos, line)
                    if token == 'async' and not stashed:
                        stashed = tok
                        continue

                    if token in ('def', 'for'):
                        if (stashed
                                and stashed[0] == NAME
                                and stashed[1] == 'async'):

                            if token == 'def':
                                async_def = True
...
if token in ('def', 'for'):
                        if (stashed
                                and stashed[0] == NAME
                                and stashed[1] == 'async'):

                            if token == 'def':
                                async_def = True
                                async_def_indent = indents[-1]

                            yield (ASYNC, stashed[1],
                                   stashed[2], stashed[3],
                                   stashed[4])
                            stashed = None

# Repair lesson:
Use the correct object attributes and preserve the local data model. Handle edge cases explicitly in the returned value.
...
```

### Baseline Generated Code, Failed
```python
def is_nested(string):
    stack = []
    for char in string:
        if char == '[':
            stack.append(char)
        elif char == ']':
            if stack:
                stack.pop()
            else:
                return False
    return len(stack) == 0
```
Failure: baseline solved balanced brackets, so it returned true for non-nested balanced strings such as `[][]`, which violates the tests.

### Structured RAG Generated Code, Passed
```python
def is_nested(string):
    opening_bracket_index = []
    closing_bracket_index = []
    for i in range(len(string)):
        if string[i] == '[':
            opening_bracket_index.append(i)
        elif string[i] == ']':
            closing_bracket_index.append(i)
    closing_bracket_index.reverse()
    cnt = 0
    i = 0
    l = len(closing_bracket_index)
    for idx in opening_bracket_index:
        if i < l and idx < closing_bracket_index[i]:
            cnt += 1
            i += 1
    return cnt >= 2
```
Why this illustrates the method: the RAG output preserves the local index-counting structure and makes the targeted value-misuse repair: use `[` and `]` instead of `(` and broad `else` handling. This is exactly the kind of local edit-pattern transfer the method is meant to encourage.

## 11. Recommended Paper Framing

- Main claim: structured failure-aware reranking improves repair-example relevance, especially edit-pattern tag compatibility.
- Secondary claim: downstream repair improves or remains competitive in controlled settings, but is sensitive to model and patch layer.
- Negative result: on HumanEvalFix and original PyBugHive large-file repair, retrieval can hurt because retrieved context does not guarantee better patch generation.
- Contamination statement: HumanEvalFix is clean relative to `repair_clean`; PyBugHive Black has a project-held-out rerun where same-project retrieval records are removed.