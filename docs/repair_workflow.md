# Repair Workflow

```mermaid
flowchart TD
    A["Benchmark case selected"] --> B["Evaluator checks out buggy repo/file"]
    B --> C["Install project dependencies"]
    C --> D["Run benchmark test command on buggy code"]
    D --> E["Collect failing signal<br/>test output / traceback / assertions"]

    E --> F{"Mode?"}

    F --> G["Baseline repair prompt builder"]
    F --> H["RAG retrieval query builder"]

    H --> I["Embed buggy code + failure signal"]
    I --> J["Search repair index"]
    J --> K["Rerank retrieved examples"]
    K --> L["Build RAG prompt<br/>buggy code + failure signal + repair lessons/examples"]

    G --> M["LLM generates repair"]
    L --> M2["LLM generates repair"]

    M --> N["Apply repair to target file"]
    M2 --> N

    N --> O["Run benchmark tests on repaired code"]
    O --> P{"Tests pass?"}

    P --> Q["Record PASS"]
    P --> R{"Retry allowed?"}

    R --> S["Build follow-up failure signal from latest test output"]
    S --> T["Second repair attempt"]
    T --> N

    R --> U["Record FAIL"]
```

## Notes

- Shared path: checkout -> install -> run tests -> collect failure signal -> generate repair -> rerun tests.
- Baseline uses `buggy_code + failure_signal`.
- RAG uses `buggy_code + failure_signal + retrieved examples / repair lessons`.
- Retry behavior depends on benchmark configuration:
  - QuixBugs best setup used multi-candidate selection.
  - PyBugHive currently benefits a lot from follow-up repair attempts with updated failure signals.
