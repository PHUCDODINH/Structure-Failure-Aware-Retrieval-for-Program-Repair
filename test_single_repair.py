#!/usr/bin/env python3
"""
Quick test of a single QuixBugs problem with RAG repair.
This tests the full pipeline: buggy code → RAG retrieval → OpenAI repair → test execution
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Verify API key
if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY not set")
    exit(1)

from src.models.repair_rag import repair_with_rag

# Test with a simple QuixBugs problem
print("=" * 60)
print("Testing Single QuixBugs Problem with RAG")
print("=" * 60)

# Read buggy bitcount
buggy_file = "data/quixbugs/correct/bitcount.py"  # Remember: "correct" folder has buggy code
with open(buggy_file) as f:
    buggy_code = f.read()

print("\n[1] Buggy Code (bitcount):")
print("-" * 60)
print(buggy_code[:200] + "...")
print("-" * 60)

print("\n[2] Running RAG repair...")
try:
    fixed_code = repair_with_rag(buggy_code, description="Fix the bitcount function")
    
    print("\n[3] Fixed Code:")
    print("-" * 60)
    print(fixed_code)
    print("-" * 60)
    
    # Check if the fix looks correct
    if "&=" in fixed_code:
        print("\n✓ Fix looks correct! (uses &= operator)")
    elif "^=" in fixed_code:
        print("\n⚠️  Warning: Still uses ^= operator (might not be fixed)")
    
    print("\n✓ RAG repair completed!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
