"""
One client over two provider SDKs.

Three things the previous version did that the configuration module said it
did not:

* ``generate()`` hardcoded ``claude-3-5-sonnet-20240620`` and ``deepseek-chat``.
  ``Config.ANTHROPIC_MODEL`` and ``Config.OPENAI_MODEL`` existed and were read
  by nothing, so changing the model in ``.env`` changed nothing -- and the
  Anthropic default is a retired model, so every Anthropic call failed.
* ``Config.LLM_TIMEOUT_SECONDS`` and ``Config.LLM_MAX_RETRIES`` were declared
  and never applied. A hung provider connection hung the request.
* Failures were ``print()``ed to stdout before being re-raised. The CLI prints
  its JSON result to stdout, so a consumer piping it received the error text
  mixed into the document.
"""

from __future__ import annotations

import logging

import anthropic
import openai

from src.core.config import Config

logger = logging.getLogger("meeting_intelligence.llm")

SUPPORTED_PROVIDERS = ("anthropic", "openai")


class LLMClient:
    def __init__(self, provider: str = "anthropic") -> None:
        self.provider = provider
        if provider == "anthropic":
            if not Config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables.")
            self.client = anthropic.Anthropic(
                api_key=Config.ANTHROPIC_API_KEY,
                timeout=Config.LLM_TIMEOUT_SECONDS,
                max_retries=Config.LLM_MAX_RETRIES,
            )
        elif provider == "openai":
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not found in environment variables.")
            self.client = openai.OpenAI(
                api_key=Config.OPENAI_API_KEY,
                base_url=Config.OPENAI_BASE_URL,
                timeout=Config.LLM_TIMEOUT_SECONDS,
                max_retries=Config.LLM_MAX_RETRIES,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @property
    def default_model(self) -> str:
        return Config.ANTHROPIC_MODEL if self.provider == "anthropic" else Config.OPENAI_MODEL

    def generate(
        self,
        system_prompt: str,
        user_content: str,
        model: str | None = None,
        max_tokens: int = 4000,
        temperature: float = 0.2,
    ) -> str:
        model = model or self.default_model
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_content}],
                )
                return response.content[0].text
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception:
            # To the log, with the traceback -- never to stdout.
            logger.exception("%s call failed (model=%s)", self.provider, model)
            raise
