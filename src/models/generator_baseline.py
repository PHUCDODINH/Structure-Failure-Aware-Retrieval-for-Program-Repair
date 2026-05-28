import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def generate_code_baseline(prompt, model: str | None = None):
    """
    Baseline model: no retrieval.
    Returns ONLY python code, no explanation.
    """
    system_prompt = (
        "You are an expert Python programmer. "
        "Write ONLY runnable Python code. "
        "NO explanation, NO comments, NO markdown."
    )

    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()
