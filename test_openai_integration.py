#!/usr/bin/env python3
"""
Test the RAG repair system with OpenAI API.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Verify API key is loaded
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ Error: OPENAI_API_KEY not found in environment")
    exit(1)

print("✓ OpenAI API key loaded")
print(f"  Key prefix: {api_key[:20]}...")

# Test RAG repair
from src.models.repair_rag import repair_with_rag

print("\n" + "=" * 60)
print("Testing RAG Repair with OpenAI")
print("=" * 60)

# Simple test case
buggy_code = """
def square(n):
    return n ** 3  # BUG: should be n ** 2
"""

print("\n[1] Buggy Code:")
print(buggy_code)

print("\n[2] Running RAG repair...")
try:
    fixed_code = repair_with_rag(buggy_code, description="Fix the square function")
    
    print("\n[3] Fixed Code:")
    print("-" * 60)
    print(fixed_code)
    print("-" * 60)
    
    print("\n✓ RAG repair completed successfully!")
    
except Exception as e:
    print(f"\n❌ Error during repair: {e}")
    import traceback
    traceback.print_exc()
