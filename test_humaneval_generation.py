#!/usr/bin/env python3
"""
Test HumanEval code generation (both baseline and RAG).
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY not set")
    exit(1)

from src.models.humaneval_generator_baseline import generate_code_baseline
from src.models.humaneval_generator_rag import generate_code_with_rag

print("=" * 70)
print("Testing HumanEval Code Generation")
print("=" * 70)

# Simple HumanEval-style prompt
test_prompt = '''def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """ Check if in given list of numbers, are any two numbers closer to each other than
    given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
    True
    """
'''

print("\n[1] Test Prompt:")
print("-" * 70)
print(test_prompt)
print("-" * 70)

# Test baseline
print("\n[2] Testing BASELINE generation...")
try:
    baseline_code = generate_code_baseline(test_prompt)
    print("\nGenerated Code (Baseline):")
    print("-" * 70)
    print(baseline_code)
    print("-" * 70)
    print("✓ Baseline generation successful!")
except Exception as e:
    print(f"❌ Baseline generation failed: {e}")
    import traceback
    traceback.print_exc()

# Test RAG
print("\n[3] Testing RAG generation...")
try:
    rag_code = generate_code_with_rag(test_prompt, k=3, force_rag=True)
    print("\nGenerated Code (RAG):")
    print("-" * 70)
    print(rag_code)
    print("-" * 70)
    print("✓ RAG generation successful!")
except Exception as e:
    print(f"❌ RAG generation failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("✓ HumanEval generator tests complete!")
print("=" * 70)
