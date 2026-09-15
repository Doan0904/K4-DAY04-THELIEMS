from __future__ import annotations

import os

from providers.openai_provider import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter uses an OpenAI-compatible Chat Completions surface."""

    def __init__(self) -> None:
        super().__init__(
            api_key_env="OPENROUTER_API_KEY",
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            # Team-wide fixed model so v0-v3 runs stay comparable. Paid variant: the
            # :free variant is capped at 50 requests/day, too few for the full lab.
            default_model=os.getenv("OPENROUTER_MODEL", "poolside/laguna-s-2.1"),
        )
