"""Key checker: tests every LLM provider key in .env and reports in plain words.

Run after adding/redeeming any key:  .\\.venv\\Scripts\\python.exe check_key.py
- OPENAI_API_KEY      -> full test (makes a tiny ~R0.002 call; also proves credits)
- AIML_API_KEY        -> validity test (lists available models; no spend)
- FEATHERLESS_API_KEY -> validity test (lists available models; no spend)
Missing keys are skipped, not errors.
"""
from dotenv import load_dotenv
load_dotenv()

import os
from openai import OpenAI


def check_openai():
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        print("OpenAI:      SKIPPED (no OPENAI_API_KEY in .env)")
        return
    try:
        client = OpenAI()
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=2,
        )
        print("OpenAI:      WORKS, has credits. Replied:", r.choices[0].message.content)
    except Exception as e:
        msg = str(e)
        if "insufficient_quota" in msg:
            print("OpenAI:      key valid but NO credits. Fix: platform.openai.com -> Billing.")
        else:
            print("OpenAI:      ERROR ->", msg[:200])


def check_compatible(name: str, key_var: str, base_url: str):
    """Any OpenAI-compatible provider: verify the key by listing models (free)."""
    key = os.getenv(key_var, "")
    if not key:
        print(f"{name}: SKIPPED (no {key_var} in .env)")
        return
    try:
        client = OpenAI(api_key=key, base_url=base_url)
        models = client.models.list()
        count = len(list(models))
        print(f"{name}: KEY VALID - {count} models available.")
    except Exception as e:
        print(f"{name}: ERROR ->", str(e)[:200])


if __name__ == "__main__":
    print("--- Checking all provider keys in .env ---")
    check_openai()
    check_compatible("AI/ML API:  ", "AIML_API_KEY",
                     os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1"))
    check_compatible("Featherless:", "FEATHERLESS_API_KEY",
                     os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"))
    print("--- Done ---")
