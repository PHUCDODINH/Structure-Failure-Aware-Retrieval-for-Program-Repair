#!/usr/bin/env python3
"""
Comprehensive test comparing baseline vs RAG repair on multiple examples.
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY not set")
    exit(1)

from src.models.repair_baseline import repair_without_rag
from src.models.repair_rag import repair_with_rag

print("=" * 70)
print("Comparing Baseline vs RAG Repair")
print("=" * 70)

# Test cases
test_cases = [
    {
        "name": "Square Function",
        "buggy": "def square(n):\n    return n ** 3",
        "description": "Fix the square function"
    },
    {
        "name": "Factorial Bug",
        "buggy": "def factorial(n):\n    if n == 0:\n        return 0  # BUG: should return 1\n    return n * factorial(n - 1)",
        "description": "Fix the factorial base case"
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*70}")
    print(f"Test {i}: {test['name']}")
    print(f"{'='*70}")
    
    print(f"\nBuggy Code:")
    print("-" * 70)
    print(test['buggy'])
    print("-" * 70)
    
    # Baseline repair
    print(f"\n[Baseline] Repairing...")
    try:
        baseline_fix = repair_without_rag(test['buggy'], test['description'])
        print("Fixed Code:")
        print(baseline_fix)
    except Exception as e:
        print(f"❌ Error: {e}")
        baseline_fix = None
    
    # RAG repair
    print(f"\n[RAG] Repairing...")
    try:
        rag_fix = repair_with_rag(test['buggy'], test['description'], k=3)
        print("Fixed Code:")
        print(rag_fix)
    except Exception as e:
        print(f"❌ Error: {e}")
        rag_fix = None

print(f"\n{'='*70}")
print("✓ Comparison complete!")
print(f"{'='*70}")
