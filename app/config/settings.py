"""
Centralized app configuration loaded from environment variables.
All settings live here — never hard-coded elsewhere.
"""
import os

# ── Gemini / LLM ──────────────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TEMPERATURE: float = float(os.environ.get("GEMINI_TEMPERATURE", "0.0"))
GEMINI_MAX_RETRIES: int = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))
GEMINI_TIMEOUT: int = int(os.environ.get("GEMINI_TIMEOUT", "30"))

# ── Versioning (used in cache keys) ───────────────────────────
FORMALIZER_VERSION: str = "1.0.0"
SCHEMA_VERSION: str = "1.0"
ONTOLOGY_VERSION: str = "1.0"
PROMPT_VERSION: str = "1.0"

# ── Cache ──────────────────────────────────────────────────────
CACHE_DB_PATH: str = os.environ.get(
    "CACHE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "app", "cache", "formalizer_cache.db")
)
