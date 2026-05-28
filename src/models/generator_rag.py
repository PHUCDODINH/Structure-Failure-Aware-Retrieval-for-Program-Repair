import json
import os
import faiss
import numpy as np
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)


# ============================================================
# CONFIG
# ============================================================
DATASET_PATH = "data/bugfix_dataset.jsonl"
FAISS_PATH = "data/index/faiss.index"
META_PATH = "data/index/meta.jsonl"
EMBED_MODEL = "all-MiniLM-L6-v2"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ============================================================
# EMBEDDING
# ============================================================
def load_embedder() -> SentenceTransformer:
    try:
        return SentenceTransformer(EMBED_MODEL, local_files_only=True)
    except Exception:
        print(f"Local cache miss for embedding model {EMBED_MODEL}; attempting download...")
        return SentenceTransformer(EMBED_MODEL)


embedder = load_embedder()

def embed(text: str) -> np.ndarray:
    return embedder.encode(text, convert_to_numpy=True).astype("float32")


# ============================================================
# BUG TYPE → FAILURE MODES (STABLE CONTRACT)
# ============================================================
BUG_TYPE_TO_FAILURE_MODES = {
    "mutate_return": [
        "Function does not return the computed result",
        "Missing return statement causes None to be returned"
    ],
    "wrong-bitwise-operation": [
        "Incorrect bit manipulation logic leads to wrong results",
        "Bit-clearing step does not correctly remove the lowest set bit"
    ],
    "incorrect-algorithm-step": [
        "Algorithmic step is implemented incorrectly"
    ],
    "unknown": [
        "Incorrect algorithmic logic"
    ]
}


# ============================================================
# BUG EXTRACTION (MULTI-FORMAT)
# ============================================================
def extract_bug_info(entry: dict) -> Tuple[List[str], List[str]]:
    """
    Priority:
    1. Explicit bug_type (MBPP-synthetic)
    2. Heuristic diff (QuixBugs)
    3. Fallback
    """
    failure_modes = []
    bug_types = []

    # ----- Explicit bug_type -----
    bug_type = entry.get("bug_type")
    if isinstance(bug_type, str) and bug_type:
        bug_types.append(bug_type)
        failure_modes.extend(
            BUG_TYPE_TO_FAILURE_MODES.get(
                bug_type,
                BUG_TYPE_TO_FAILURE_MODES["unknown"]
            )
        )
        return failure_modes, bug_types

    # ----- Heuristic (example: bitcount XOR vs AND) -----
    buggy = entry.get("buggy_code", "")
    fixed = entry.get("fixed_code", "")

    if "^=" in buggy and "&=" in fixed:
        bug_types.extend([
            "wrong-bitwise-operation",
            "incorrect-algorithm-step"
        ])
        failure_modes.extend(
            BUG_TYPE_TO_FAILURE_MODES["wrong-bitwise-operation"]
        )

    # ----- Fallback -----
    if not failure_modes:
        bug_types.append("unknown")
        failure_modes.extend(BUG_TYPE_TO_FAILURE_MODES["unknown"])

    return failure_modes, bug_types


# ============================================================
# PROMPT EXTRACTION (GUARANTEED NON-EMPTY)
# ============================================================
def extract_prompt(entry: dict) -> str:
    """
    ALWAYS returns a valid, non-empty prompt string.
    """
    # Prefer explicit prompt
    prompt = entry.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()

    # Fallback: extract docstring
    code = entry.get("buggy_code", "")
    if isinstance(code, str) and '"""' in code:
        extracted = code.split('"""', 1)[1].strip()
        if extracted:
            return extracted

    # Final fallback
    return "Solve the programming task described by this problem."


# ============================================================
# METADATA CONSTRUCTION (SCHEMA GUARANTEED)
# ============================================================
def build_metadata_entry(entry: dict) -> dict:
    failure_modes, bug_types = extract_bug_info(entry)

    return {
        "id": entry.get("id", "unknown"),
        "source": entry.get("source", "unknown"),
        "prompt": extract_prompt(entry),                 # ALWAYS EXISTS
        "common_failure_modes": failure_modes or [],     # ALWAYS EXISTS
        "bug_types": bug_types or ["unknown"]            # ALWAYS EXISTS
    }


# ============================================================
# BUILD FAISS INDEX (RUN ONCE)
# ============================================================
def build_faiss_index():
    raw = [json.loads(x) for x in open(DATASET_PATH)]

    vectors = []
    metadata = []

    for entry in raw:
        meta = build_metadata_entry(entry)

        embed_text = (
            meta["prompt"]
            + "\nCommon mistakes:\n"
            + " ".join(meta["common_failure_modes"])
        )

        vectors.append(embed(embed_text))
        metadata.append(meta)

    vectors = np.vstack(vectors)
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, FAISS_PATH)

    with open(META_PATH, "w") as f:
        for m in metadata:
            f.write(json.dumps(m) + "\n")


# ============================================================
# LOAD INDEX + METADATA (DEFENSIVE)
# ============================================================
def load_index_and_metadata():
    index = faiss.read_index(FAISS_PATH)
    meta = [json.loads(x) for x in open(META_PATH)]

    # Enforce schema safety (old files)
    for m in meta:
        m.setdefault("prompt", "Solve the programming task described by this problem.")
        m.setdefault("common_failure_modes", [])
        m.setdefault("bug_types", ["unknown"])

    return index, meta


faiss_index, metadata = load_index_and_metadata()


# ============================================================
# RETRIEVAL (NO KEYERROR POSSIBLE)
# ============================================================
def retrieve_examples(query: str, k: int = 5):
    print(">>> USING retrieve_examples FROM:", __file__)
    q_vec = embed(query).reshape(1, -1)
    _, idxs = faiss_index.search(q_vec, k)

    prompts = []
    bug_hints = []

    for i in idxs[0]:
        item = metadata[i]

        # ✅ SAFE prompt access (never KeyError)
        p = item.get("prompt")
        if isinstance(p, str) and p.strip():
            prompts.append(p)
        else:
            # absolute fallback
            prompts.append(
                "Solve the programming task described by this problem."
            )

        # ✅ SAFE bug hint access
        bug_hints.extend(item.get("common_failure_modes", []))

    return prompts, sorted(set(bug_hints))

# ============================================================
# PROMPT CONSTRUCTION
# ============================================================
def build_generation_prompt(
    task_prompt: str,
    context_prompts: List[str],
    bug_hints: List[str]
) -> str:
    header = (
        "You are an expert Python programmer.\n"
        "Write ONLY runnable Python code.\n"
        "NO comments, NO markdown, NO explanations.\n"
        "The code must define EXACTLY the function described.\n\n"
    )

    context_block = ""
    for p in context_prompts:
        context_block += f"# Similar problem:\n{p}\n\n"

    bug_block = ""
    if bug_hints:
        bug_block = (
            "# Common mistakes in similar problems:\n"
            + "\n".join(f"- {b}" for b in bug_hints)
            + "\n\n"
        )

    final_block = (
        "# Now solve this new problem carefully:\n"
        f"{task_prompt}\n"
        "# Your solution:\n"
    )

    return header + context_block + bug_block + final_block


# ============================================================
# CODE GENERATION
# ============================================================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_code_with_rag(
    task_prompt: str,
    k: int = 5,
    model: str | None = None
) -> str:
    ctx, bug_hints = retrieve_examples(task_prompt, k)
    final_prompt = build_generation_prompt(task_prompt, ctx, bug_hints)

    print("=== FINAL PROMPT SENT TO MODEL ===")
    print(final_prompt)
    print("=================================")

    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=[{"role": "user", "content": final_prompt}],
        temperature=0
    )

    return response.choices[0].message.content.strip()


def generate_code_with_rag_mbpp(
    prompt: str,
    k: int = 5,
    model: str | None = None
) -> str:
    user_prompt = (
        "Write ONLY Python code.\n"
        "Define EXACTLY one function named `solution`.\n"
        "Do NOT add comments or explanations.\n\n"
        f"{prompt}\n\n"
        "def solution("
    )
    return generate_code_with_rag(user_prompt, k, model=model)


# ============================================================
# DEBUG
# ============================================================
if __name__ == "__main__":
    demo = "Write a function that counts the number of 1 bits in a nonnegative integer."
    print(generate_code_with_rag(demo))
