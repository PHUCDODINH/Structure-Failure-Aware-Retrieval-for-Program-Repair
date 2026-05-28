import os
import time
import random
from openai import APIConnectionError, OpenAI, RateLimitError
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    max_retries=0,
)
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "30"))
MAX_API_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def safe_chat_completion(model, messages, temperature=0, max_retries=MAX_API_RETRIES):
    """
    Retry logic for OpenAI API calls to handle RateLimitError.
    """
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (RateLimitError, APIConnectionError) as e:
            if attempt == max_retries - 1:
                print(f"[ERROR] Max retries reached for transient OpenAI error: {e}")
                raise
            
            print(f"[WARNING] Transient OpenAI error. Retrying in {delay:.2f}s... (Attempt {attempt+1}/{max_retries})")
            time.sleep(delay)
            delay *= 2
            delay += random.uniform(0, 0.5)
            
    return None


def generate_code_baseline(prompt: str, model: str | None = None):
    """
    Safe baseline generator:
    - Takes only the HumanEval prompt (function signature + docstring)
    - Returns ONLY Python code
    - No explanations, comments, or markdown
    """
    system_prompt = (
        "You are an expert Python programmer.\n"
        "Write ONLY runnable Python code.\n"
        "NO comments, NO explanations, NO markdown.\n"
        "Output ONLY the function implementation.\n"
    )

    # 🔹 PRINT PROMPT HERE
    print("=== PROMPT SENT TO MODEL ===")
    print(prompt)
    print("============================")

    response = safe_chat_completion(
        model=model or DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return _strip_code_fences(response.choices[0].message.content)


def generate_code_baseline_mbpp(prompt):
    user_prompt = (
        "Write ONLY Python code.\n"
        "Define EXACTLY one function named `solution` that solves this problem.\n"
        "Do NOT add comments or explanations.\n\n"
        f"{prompt}\n\n"
        "def solution("
    )

    code = generate_code_baseline(user_prompt)
    return code
