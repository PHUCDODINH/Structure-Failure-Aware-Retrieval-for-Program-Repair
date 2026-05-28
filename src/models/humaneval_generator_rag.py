import json
import os
import time
import random
import difflib
import re
from typing import List, Dict
from openai import APIConnectionError, OpenAI, RateLimitError
from dotenv import load_dotenv
from src.retrieval.index_store import embed_text, load_index_bundle

# Load environment variables
load_dotenv(override=True)


# ============================================================
# CONFIG
# ============================================================
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "30"))
MAX_API_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
MAX_RAG_EXAMPLES = 2
SEARCH_POOL_SIZE = 24
MAX_DIFF_HUNKS = 2
DIFF_CONTEXT_LINES = 6
MAX_SNIPPET_CHARS = 1200
MAX_CONTEXT_CHARS = 5000
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ============================================================
# SAFE ACCESSORS
# ============================================================
def safe_get_buggy_code(item: dict) -> str:
    c = item.get("buggy_code")
    if isinstance(c, str) and c.strip():
        return c
    return "# No buggy code available"

def safe_get_fixed_code(item: dict) -> str:
    c = item.get("fixed_code") or item.get("code") # Fallback for non-bugfix entries if any
    if isinstance(c, str) and c.strip():
        return c
    return "# No fixed code available"


def _truncate_text(text: str, max_chars: int = MAX_SNIPPET_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    keep = max_chars // 2
    return text[:keep].rstrip() + "\n...\n" + text[-keep:].lstrip()


def _focused_diff_snippet(buggy: str, fixed: str) -> tuple[str, str]:
    buggy_lines = buggy.splitlines()
    fixed_lines = fixed.splitlines()
    matcher = difflib.SequenceMatcher(a=buggy_lines, b=fixed_lines)

    buggy_chunks: list[str] = []
    fixed_chunks: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        buggy_start = max(0, i1 - DIFF_CONTEXT_LINES)
        buggy_end = min(len(buggy_lines), i2 + DIFF_CONTEXT_LINES)
        fixed_start = max(0, j1 - DIFF_CONTEXT_LINES)
        fixed_end = min(len(fixed_lines), j2 + DIFF_CONTEXT_LINES)

        buggy_chunks.append("\n".join(buggy_lines[buggy_start:buggy_end]).strip())
        fixed_chunks.append("\n".join(fixed_lines[fixed_start:fixed_end]).strip())

        if len(buggy_chunks) >= MAX_DIFF_HUNKS:
            break

    if not buggy_chunks or not fixed_chunks:
        return _truncate_text(buggy), _truncate_text(fixed)

    buggy_text = "\n...\n".join(chunk for chunk in buggy_chunks if chunk)
    fixed_text = "\n...\n".join(chunk for chunk in fixed_chunks if chunk)
    return _truncate_text(buggy_text), _truncate_text(fixed_text)


def _extract_identifiers(text: str) -> set[str]:
    return {
        token.lower()
        for token in IDENTIFIER_RE.findall(text)
        if len(token) > 2 and token.lower() not in {"def", "for", "while", "return", "true", "false", "none"}
    }


def _scope_bonus(metadata: dict) -> float:
    scope = metadata.get("scope")
    if scope == "function":
        return 0.35
    if scope == "method":
        return 0.2
    if scope == "small_module":
        return 0.1
    return 0.0


def _length_similarity(query: str, candidate_code: str) -> float:
    query_tokens = max(1, len(query.split()))
    candidate_tokens = max(1, len(candidate_code.split()))
    return min(query_tokens, candidate_tokens) / max(query_tokens, candidate_tokens)


def _rerank_score(query: str, candidate: dict, dense_rank: int) -> float:
    candidate_buggy = safe_get_buggy_code(candidate)
    metadata = candidate.get("metadata", {})
    query_ids = _extract_identifiers(query)
    candidate_ids = _extract_identifiers(candidate_buggy)
    overlap = len(query_ids & candidate_ids) / max(1, len(query_ids))

    changed_lines = min(int(metadata.get("changed_lines", 0) or 0), 120)
    files_changed = int(metadata.get("files_changed", 1) or 1)
    file_bonus = 0.2 if files_changed == 1 else 0.0
    size_penalty = changed_lines / 450.0
    dense_bonus = 1.0 / (dense_rank + 1)
    length_bonus = _length_similarity(query, candidate_buggy) * 0.25
    framework_penalty = 0.15 if metadata.get("framework_heavy") else 0.0

    return dense_bonus + overlap + _scope_bonus(metadata) + file_bonus + length_bonus - size_penalty - framework_penalty


def _infer_generation_lesson(example: Dict[str, str]) -> str:
    buggy_snippet, fixed_snippet = _focused_diff_snippet(
        example["buggy"],
        example["fixed"],
    )
    changed_text = f"{buggy_snippet}\n{fixed_snippet}".lower()
    lessons: list[str] = []

    if any(token in changed_text for token in ("if ", "elif ", "while ", "for ", "range(", "<=", ">=", "==", "!=")):
        lessons.append("Check boundary conditions and branch logic before writing the final loop or condition.")
    if "return" in changed_text:
        lessons.append("Match the final return value and output shape exactly to the required contract.")
    if any(token in changed_text for token in ("[", "]", ".append", ".pop", ".sort", "sorted(")):
        lessons.append("Be careful with indexing, collection updates, and result ordering.")
    if any(token in changed_text for token in ("+", "-", "*", "/", "%", "sum(", "max(", "min(")):
        lessons.append("Verify arithmetic updates and accumulator state step by step.")

    if not lessons:
        lessons.append("Transfer only the local correction pattern, not the repository-specific structure.")

    return " ".join(lessons[:2])


def _format_example(example: Dict[str, str], index: int) -> str:
    buggy_snippet, fixed_snippet = _focused_diff_snippet(
        example["buggy"],
        example["fixed"],
    )
    return (
        f"--- Example {index} ({example['source']}) ---\n"
        "[Transfer Lesson]:\n"
        f"{example['lesson']}\n\n"
        "[Buggy Snippet]:\n"
        f"{buggy_snippet}\n\n"
        "[Fixed Snippet]:\n"
        f"{fixed_snippet}\n\n"
    )


# ============================================================
# RETRIEVAL
# ============================================================
def retrieve_examples(
    query: str,
    k: int = MAX_RAG_EXAMPLES,
    force_rag: bool = False,
    retrieval_profile: str | None = None,
    index_dir: str | None = None,
) -> List[Dict[str, str]]:
    faiss_index, metadata = load_index_bundle(profile=retrieval_profile, index_dir=index_dir)
    if faiss_index is None:
        return []

    q_vec = embed_text(query).reshape(1, -1)
    pool_size = min(len(metadata), max(k, SEARCH_POOL_SIZE))
    _, idxs = faiss_index.search(q_vec, pool_size)

    ranked: list[tuple[float, dict]] = []
    seen_ids = set()

    for dense_rank, idx in enumerate(idxs[0]):
        if idx == -1:
            continue

        item = metadata[idx]
        uid = item.get("id", str(idx))
        if uid in seen_ids:
            continue
        seen_ids.add(uid)

        ranked.append((_rerank_score(query, item, dense_rank), item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)

    examples = []
    for _, item in ranked[:k]:
        example = {
            "buggy": safe_get_buggy_code(item),
            "fixed": safe_get_fixed_code(item),
            "source": item.get("source", "unknown"),
        }
        example["lesson"] = _infer_generation_lesson(example)
        examples.append(example)

    return examples


# ============================================================
# PROMPT CONSTRUCTION
# ============================================================
def build_generation_prompt(
    task_prompt: str,
    examples: List[Dict[str, str]]
) -> str:

    header = (
        "You are an expert Python programmer.\n"
        "Your task is to write a Python function that solves the described problem.\n"
        "Return ONLY the code, starting with the function definition.\n"
        "NO markdown, NO comments outside the code, NO explanations.\n\n"
    )

    context_block = ""
    if examples:
        context_block = (
            "Here are compact examples of similar bugs and their fixes.\n"
            "Focus on the transfer lesson and correction pattern, not the project-specific details.\n\n"
        )
        used_chars = len(context_block)
        for i, ex in enumerate(examples[:MAX_RAG_EXAMPLES], start=1):
            formatted = _format_example(ex, i)
            if used_chars + len(formatted) > MAX_CONTEXT_CHARS:
                break
            context_block += formatted
            used_chars += len(formatted)
        context_block += "---\n\n"

    final_block = (
        "Now, solve the following problem correctly:\n"
        f"Problem:\n{task_prompt}\n\n"
        "Solution:\n"
    )

    return header + context_block + final_block


# ============================================================
# CODE GENERATION (MAIN ENTRY)
# ============================================================
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    max_retries=0,
)

def safe_chat_completion(model, messages, temperature=0, max_retries=MAX_API_RETRIES):
    """
    Retry logic for OpenAI API calls to handle RateLimitError.
    Uses exponential backoff with jitter.
    """
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (RateLimitError, APIConnectionError) as e:
            if attempt == max_retries - 1:
                print(f"[ERROR] Max retries reached for transient OpenAI error: {e}")
                raise
            
            print(f"[WARNING] Transient OpenAI error. Retrying in {delay:.2f}s... (Attempt {attempt+1}/{max_retries})")
            time.sleep(delay)
            # Exponential backoff with jitter
            delay *= 2
            delay += random.uniform(0, 0.5)
            
    return None # Should not reach here

def generate_code_with_rag(
    task_prompt: str,
    k: int = MAX_RAG_EXAMPLES,
    force_rag: bool = False,
    model: str | None = None,
    retrieval_profile: str | None = None,
    index_dir: str | None = None,
) -> str:

    examples = retrieve_examples(
        task_prompt,
        k=k,
        force_rag=force_rag,
        retrieval_profile=retrieval_profile,
        index_dir=index_dir,
    )

    final_prompt = build_generation_prompt(
        task_prompt,
        examples
    )

    # DEBUG PRINT
    # print("=== FINAL PROMPT SENT TO MODEL ===")
    # print(final_prompt[:500] + "... (truncated)") 
    # print("=================================")

    # Use safe completion with retry
    response = safe_chat_completion(
        model=model or DEFAULT_MODEL,
        messages=[{"role": "user", "content": final_prompt}],
        temperature=0
    )

    return _strip_code_fences(response.choices[0].message.content)
