#!/usr/bin/env python3
"""
Test script to verify the dataset is correctly structured.
Checks that buggy/correct code pairs are properly labeled.
"""

import json
import os
import sys

def test_dataset():
    print("=" * 60)
    print("Testing Dataset Structure")
    print("=" * 60)
    
    # Test 1: Check files exist
    print("\n[TEST 1] Checking dataset files exist...")
    
    quixbugs_file = "data/quixbugs/quixbugs_bugfix.jsonl"
    combined_file = "data/all_bugfix_pairs.jsonl"
    
    if not os.path.exists(quixbugs_file):
        print(f"✗ QuixBugs dataset not found: {quixbugs_file}")
        return False
    print(f"✓ Found QuixBugs dataset: {quixbugs_file}")
    
    if not os.path.exists(combined_file):
        print(f"✗ Combined dataset not found: {combined_file}")
        return False
    print(f"✓ Found combined dataset: {combined_file}")
    
    # Test 2: Check dataset structure
    print("\n[TEST 2] Checking dataset structure...")
    
    with open(combined_file) as f:
        lines = f.readlines()
        total = len(lines)
        print(f"✓ Total examples in combined dataset: {total}")
        
        if total == 0:
            print("✗ Dataset is empty!")
            return False
    
    # Test 3: Verify a known example (bitcount)
    print("\n[TEST 3] Verifying known example (bitcount)...")
    
    bitcount_found = False
    with open(combined_file) as f:
        for line in f:
            item = json.loads(line)
            if item.get("id") == "bitcount":
                bitcount_found = True
                
                buggy = item.get("buggy_code", "")
                fixed = item.get("fixed_code", item.get("correct_code", ""))
                
                # The buggy version should have ^= (XOR)
                # The fixed version should have &= (AND)
                has_xor_in_buggy = "^=" in buggy
                has_and_in_fixed = "&=" in fixed
                
                print(f"  Buggy code contains '^=' (XOR): {has_xor_in_buggy}")
                print(f"  Fixed code contains '&=' (AND): {has_and_in_fixed}")
                
                if has_xor_in_buggy and has_and_in_fixed:
                    print("✓ Bitcount example is correctly labeled!")
                else:
                    print("✗ Bitcount example labels are SWAPPED or incorrect!")
                    print("\n  Buggy code snippet:")
                    print("  " + "\n  ".join(buggy.split("\n")[:10]))
                    print("\n  Fixed code snippet:")
                    print("  " + "\n  ".join(fixed.split("\n")[:10]))
                    return False
                break
    
    if not bitcount_found:
        print("✗ Bitcount example not found in dataset")
        return False
    
    # Test 4: Check all examples have required fields
    print("\n[TEST 4] Checking all examples have required fields...")
    
    missing_fields = []
    with open(combined_file) as f:
        for i, line in enumerate(f):
            item = json.loads(line)
            
            if "buggy_code" not in item:
                missing_fields.append((i, "buggy_code"))
            
            if "fixed_code" not in item and "correct_code" not in item:
                missing_fields.append((i, "fixed_code/correct_code"))
    
    if missing_fields:
        print(f"✗ Found {len(missing_fields)} examples with missing fields:")
        for idx, field in missing_fields[:5]:  # Show first 5
            print(f"  Line {idx}: missing {field}")
        return False
    
    print("✓ All examples have required fields")
    
    print("\n" + "=" * 60)
    print("All dataset tests passed! ✓")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_dataset()
    sys.exit(0 if success else 1)
