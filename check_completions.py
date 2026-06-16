"""One-off: prove the partner credits actually pay for completions.
Sends one tiny prompt to AI/ML API and one to Featherless. Safe to delete.
"""
from dotenv import load_dotenv
load_dotenv()

import os
from openai import OpenAI


def try_chat(name, key_var, base_var, default_base, model):
    try:
        client = OpenAI(api_key=os.getenv(key_var),
                        base_url=os.getenv(base_var, default_base))
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=4,
        )
        print(f"{name}: COMPLETIONS WORK ({model}) -> {r.choices[0].message.content!r}")
    except Exception as e:
        print(f"{name}: FAILED ({model}) -> {str(e)[:250]}")


if __name__ == "__main__":
    try_chat("AI/ML API ", "AIML_API_KEY", "AIML_BASE_URL",
             "https://api.aimlapi.com/v1", "gpt-4o-mini")
    try_chat("Featherless", "FEATHERLESS_API_KEY", "FEATHERLESS_BASE_URL",
             "https://api.featherless.ai/v1", "meta-llama/Meta-Llama-3.1-8B-Instruct")
