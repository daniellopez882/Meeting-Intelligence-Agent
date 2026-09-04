"""
src/core/config.py
Configuration, read from the environment.

The previous version was three class attributes evaluated at import time, with
no validation and no notion of environment. It also had no API key setting at
all -- the HTTP endpoint that calls an LLM was open to anyone who could reach
it.

A note on .env: this repository committed one containing a live DeepSeek API
key. A later commit blanked the value, which does not remove it from git
history. Rotate any key that has ever been committed; .env is now ignored.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

INSECURE_API_KEY = "changeme-in-production"


def _split(value: str | None) -> list[str]:
    """Comma-separated or JSON-ish list from an environment variable."""
    if not value:
        return []
    return [item.strip() for item in value.strip("[]").replace('"', "").split(",") if item.strip()]


class Config:
    # ---- Environment -------------------------------------------------------
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    IS_PRODUCTION = ENVIRONMENT == "production"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # ---- HTTP --------------------------------------------------------------
    API_KEY = os.getenv("API_KEY", INSECURE_API_KEY)
    CORS_ALLOW_ORIGINS = _split(os.getenv("CORS_ALLOW_ORIGINS"))

    # ---- Model providers ---------------------------------------------------
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = (
        os.getenv("OPENAI_API_KEY") or os.getenv("KIMI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    )
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")

    # Defaults were claude-3-5-sonnet-20240620 and deepseek-chat, both pinned
    # in the client. They are configuration now.
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

    # ---- Request handling --------------------------------------------------
    LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

    @classmethod
    def has_insecure_api_key(cls) -> bool:
        return cls.API_KEY == INSECURE_API_KEY

    @classmethod
    def validate_production(cls) -> None:
        """Refuse to serve production traffic on an unsafe configuration."""
        problems: list[str] = []
        if cls.has_insecure_api_key():
            problems.append(
                "API_KEY is still the placeholder; the model endpoint would be open. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        if not (cls.OPENAI_API_KEY or cls.ANTHROPIC_API_KEY):
            problems.append("No model provider key is configured.")
        if not cls.CORS_ALLOW_ORIGINS:
            problems.append("CORS_ALLOW_ORIGINS is empty; browsers would be refused.")
        if problems:
            raise ValueError("Invalid production configuration:\n  - " + "\n  - ".join(problems))
