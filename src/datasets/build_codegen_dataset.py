import json
import os
import ast
import re

# Input paths
MBPP_PATH = "data/mbpp/mbpp_correct.jsonl"
HUMANEVAL_PATH = "data/humaneval/HumanEval.jsonl"
QUIXBUGS_PATH = "data/quixbugs/quixbugs_bugfix.jsonl"

# Output path
OUTPUT_PATH = "data/codegen_examples.jsonl"

def extract_docstring(code):
    """
    Extracts docstring from code using AST.
    Falls back to regex if AST parsing fails.
    """
    try:
        tree = ast.parse(code)
        docstring = ast.get_docstring(tree)
        if docstring:
            return docstring
    except Exception:
        pass
    
    # Fallback: basic regex for triple-quote strings
    match = re.search(r'"""(.*?)"""', code, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    return ""

def main():
    examples = []
    
    # 1. Process MBPP
    print(f"Processing MBPP from {MBPP_PATH}...")
    if os.path.exists(MBPP_PATH):
        with open(MBPP_PATH, "r") as f:
            for line in f:
                item = json.loads(line)
                examples.append({
                    "id": f"mbpp_{item['id']}",
                    "source": "mbpp",
                    "prompt": item["prompt"],
                    "code": item["correct_code"],
                    "original_id": item["id"]
                })
    else:
        print(f"WARNING: {MBPP_PATH} not found.")

    # 2. Process HumanEval
    print(f"Processing HumanEval from {HUMANEVAL_PATH}...")
    if os.path.exists(HUMANEVAL_PATH):
        with open(HUMANEVAL_PATH, "r") as f:
            for line in f:
                item = json.loads(line)
                examples.append({
                    "id": f"humaneval_{item['task_id'].replace('/', '_')}",
                    "source": "humaneval",
                    "prompt": item["prompt"],
                    "code": item["canonical_solution"],
                    "original_id": item["task_id"]
                })
    else:
        print(f"WARNING: {HUMANEVAL_PATH} not found.")
        
    # 3. Process QuixBugs (Extract prompts from docstrings)
    print(f"Processing QuixBugs from {QUIXBUGS_PATH}...")
    if os.path.exists(QUIXBUGS_PATH):
        with open(QUIXBUGS_PATH, "r") as f:
            for line in f:
                item = json.loads(line)
                buggy_code = item["buggy_code"]
                prompt = extract_docstring(buggy_code)
                
                if not prompt:
                    print(f"WARNING: No docstring found for QuixBugs {item['id']}")
                    prompt = item["id"] # Fallback to ID if no docstring
                
                examples.append({
                    "id": f"quixbugs_{item['id']}",
                    "source": "quixbugs",
                    "prompt": prompt,
                    "code": item["fixed_code"],
                    "buggy_code": item["buggy_code"], # Keep for reference
                    "original_id": item["id"]
                })
    else:
        print(f"WARNING: {QUIXBUGS_PATH} not found.")

    # Save combined dataset
    print(f"Saving {len(examples)} examples to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
            
    print("Done!")

if __name__ == "__main__":
    main()
