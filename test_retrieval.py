#!/usr/bin/env python3
"""
Test script to verify the FAISS retrieval system is working correctly.
"""

import json
import sys

def test_retrieval():
    print("=" * 60)
    print("Testing RAG Retrieval System")
    print("=" * 60)
    
    # Test 1: Import modules
    print("\n[TEST 1] Importing modules...")
    try:
        from src.models.repair_rag import retrieve_examples, embed
        print("✓ Successfully imported retrieval functions")
    except Exception as e:
        print(f"✗ Failed to import: {e}")
        return False
    
    # Test 2: Test embedding
    print("\n[TEST 2] Testing embedding generation...")
    try:
        test_code = "def test(): pass"
        vec = embed(test_code)
        print(f"✓ Generated embedding with shape: {vec.shape}")
        print(f"  Dimension: {vec.shape[0]}")
    except Exception as e:
        print(f"✗ Failed to generate embedding: {e}")
        return False
    
    # Test 3: Test retrieval
    print("\n[TEST 3] Testing retrieval...")
    try:
        buggy_code = """
def bitcount(n):
    count = 0
    while n:
        n ^= n - 1  # This might be buggy
        count += 1
    return count
"""
        examples = retrieve_examples(buggy_code, k=3)
        print(f"✓ Retrieved {len(examples)} examples")
        
        # Verify structure
        if len(examples) > 0:
            first = examples[0]
            has_buggy = "buggy_code" in first
            has_fixed = "fixed_code" in first or "correct_code" in first
            
            print(f"  Example structure check:")
            print(f"    - Has 'buggy_code': {has_buggy}")
            print(f"    - Has 'fixed_code' or 'correct_code': {has_fixed}")
            
            if has_buggy and has_fixed:
                print("✓ Example structure is correct")
            else:
                print("✗ Example structure is incorrect")
                return False
    except Exception as e:
        print(f"✗ Failed to retrieve examples: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Display sample retrieved example
    print("\n[TEST 4] Sample retrieved example:")
    if len(examples) > 0:
        sample = examples[0]
        print(f"  ID: {sample.get('id', 'N/A')}")
        print(f"  Source: {sample.get('source', 'N/A')}")
        
        buggy = sample.get('buggy_code', '')[:100]
        fixed = sample.get('fixed_code', sample.get('correct_code', ''))[:100]
        
        print(f"  Buggy code (first 100 chars): {buggy}...")
        print(f"  Fixed code (first 100 chars): {fixed}...")
        print("✓ Sample example displayed")
    
    print("\n" + "=" * 60)
    print("All retrieval tests passed! ✓")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_retrieval()
    sys.exit(0 if success else 1)
