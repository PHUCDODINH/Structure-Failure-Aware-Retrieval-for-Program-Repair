#!/usr/bin/env python3
"""
Diagnostic script to show what's being retrieved for HumanEval.
This demonstrates why RAG retrieval may not be optimal for code generation.
"""

import json
from src.models.humaneval_generator_rag import retrieve_examples

# HumanEval problem
problem = """
def digits(n):
    \"\"\"Given a positive integer n, return the product of the odd digits.
    Return 0 if all digits are even.
    For example:
    digits(1)  == 1
    digits(4)  == 0
    digits(235) == 15
    \"\"\"
"""

print("=" * 70)
print("RAG Retrieval Diagnostic for HumanEval")
print("=" * 70)

print("\n[Problem]")
print(problem)

print("\n[Retrieved Examples]")
context_prompts, bug_hints = retrieve_examples(problem, k=3, force_rag=True)

print(f"\nRetrieved {len(context_prompts)} context prompts:")
for i, prompt in enumerate(context_prompts, 1):
    print(f"\n{i}. {prompt[:100]}...")

print(f"\nBug hints: {bug_hints}")

print("\n" + "=" * 70)
print("ISSUE IDENTIFIED:")
print("=" * 70)
print("""
The current FAISS index was built from BUG-FIX pairs (buggy→fixed code).
This is great for bug REPAIR but not ideal for code GENERATION.

For code generation, you want:
- Clean, correct code examples
- Similar algorithmic patterns
- Not bug-fix pairs

RECOMMENDATIONS:
1. Use BASELINE mode for HumanEval (no RAG)
2. Build a separate index from clean code examples
3. Or accept that RAG may not help much for generation tasks
""")
