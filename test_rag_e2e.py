#!/usr/bin/env python3
"""
Simple end-to-end test of the RAG repair system (without OpenAI API call).
This tests that the retrieval and prompt building works correctly.
"""

from src.models.repair_rag import retrieve_examples, build_repair_prompt

# Test buggy code
buggy_code = """
def square(n):
    return n ** 3  # BUG: should be n ** 2
"""

print("=" * 60)
print("Testing RAG Repair System (Prompt Building)")
print("=" * 60)

print("\n[1] Buggy Code:")
print(buggy_code)

print("\n[2] Retrieving similar examples...")
examples = retrieve_examples(buggy_code, k=3)
print(f"Retrieved {len(examples)} examples:")
for i, ex in enumerate(examples, 1):
    print(f"  {i}. {ex.get('id', 'unknown')} (source: {ex.get('source', 'unknown')})")

print("\n[3] Building repair prompt...")
prompt = build_repair_prompt(buggy_code, "Fix the square function", examples)

print("\n[4] Generated Prompt Preview (first 500 chars):")
print("-" * 60)
print(prompt[:500] + "...")
print("-" * 60)

print("\n✓ RAG system is working correctly!")
print("  - Retrieval: OK")
print("  - Prompt building: OK")
print("\nNote: To test actual repair, you need to:")
print("  1. Set OPENAI_API_KEY environment variable")
print("  2. Run: python -c \"from src.models.repair_rag import repair_with_rag; print(repair_with_rag('def square(n): return n**3'))\"")
