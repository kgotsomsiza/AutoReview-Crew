"""Loads configuration from environment variables (your .env file).

Designed to run even before you've installed dependencies or added any keys,
so the simulation works out of the box.
"""
import os

# Try to load a .env file if python-dotenv is installed. If it isn't yet,
# we just skip it — the simulation doesn't need real keys.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# --- Band ---
BAND_API_KEY = os.getenv("BAND_API_KEY", "")
BAND_ROOM_ID = os.getenv("BAND_ROOM_ID", "")

# --- OpenAI (used by Band's SDK quickstart; also a fallback LLM provider) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- What to review: a real public GitHub PR (Increment 2) ---
# Format: REVIEW_REPO="owner/name", REVIEW_PR="number". Leave blank to review the
# built-in sample diff instead (so the demo works offline / before a repo exists).
REVIEW_REPO = os.getenv("REVIEW_REPO", "")
REVIEW_PR = os.getenv("REVIEW_PR", "")

# --- Model provider (AI/ML API) ---
AIML_API_KEY = os.getenv("AIML_API_KEY", "")
AIML_BASE_URL = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")

# --- Model provider (Featherless - open-source models, for the Security Reviewer) ---
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")

# A different model per reviewer = "cross-model review". Four model FAMILIES
# across two partner providers. All verified for tool calling (probe_models.py,
# June 12) - non-negotiable, since Band agents reply via the send-message tool.
CORRECTNESS_MODEL = os.getenv("CORRECTNESS_MODEL", "google/gemini-2.5-flash")
CORRECTNESS_PROVIDER = os.getenv("CORRECTNESS_PROVIDER", "aiml")
SECURITY_MODEL = os.getenv("SECURITY_MODEL", "Qwen/Qwen2.5-72B-Instruct")
SECURITY_PROVIDER = os.getenv("SECURITY_PROVIDER", "featherless")
LEAD_MODEL = os.getenv("LEAD_MODEL", "gpt-4o")  # synthesis only (no tools) -> strong model is safe
LEAD_PROVIDER = os.getenv("LEAD_PROVIDER", "aiml")
TEST_MODEL = os.getenv("TEST_MODEL", "google/gemini-2.5-flash")
TEST_PROVIDER = os.getenv("TEST_PROVIDER", "aiml")


def llm_settings(provider: str) -> tuple[str, str]:
    """Map a provider name to (api_key, base_url) for OpenAI-compatible clients."""
    if provider == "aiml":
        return AIML_API_KEY, AIML_BASE_URL
    if provider == "featherless":
        return FEATHERLESS_API_KEY, FEATHERLESS_BASE_URL
    return OPENAI_API_KEY, "https://api.openai.com/v1"


def have_real_credentials() -> bool:
    """True only when we have what we need to talk to Band + a model for real.

    Until then, main.py runs in simulation mode.
    """
    return bool(BAND_API_KEY and AIML_API_KEY)
