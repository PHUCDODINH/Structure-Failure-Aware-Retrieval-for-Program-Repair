from src.models.humaneval_generator_rag import retrieve_examples

def inspect(query):
    print(f"\nQUERY: '{query}'")
    print("=" * 60)
    examples = retrieve_examples(query, k=3)
    
    for i, ex in enumerate(examples):
        print(f"--- Result {i+1} [{ex['source']}] ---")
        print(f"PROMPT: {ex['prompt'][:100]}...") 
        print(f"CODE START: {ex['code'][:100]}...")
        print("-" * 30)

if __name__ == "__main__":
    # Test 1: Generic coding task (likely MBPP/HumanEval)
    inspect("Write a function to check if a number is prime")
    
    # Test 2: Task that might match QuixBugs (e.g., bitcount, hanoi)
    inspect("Write a function to count set bits in a number")
    inspect("Write a function to solve Towers of Hanoi")
    inspect("Write a function to flatten a nested list")
