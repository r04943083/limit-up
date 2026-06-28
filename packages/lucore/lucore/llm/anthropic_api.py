"""Anthropic API provider. Optional, paid, highest quality, no local Claude needed.

Off by default; enable with LU_LLM_PROVIDER=anthropic and LU_ANTHROPIC_API_KEY=...
"""
from __future__ import annotations

import httpx

from ..config import get_settings
from .base import LLMError, LLMProvider

_ENDPOINT = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8", timeout: int = 120) -> None:
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        s = get_settings()
        key = s.anthropic_api_key
        if not key:
            raise LLMError("Anthropic provider requires LU_ANTHROPIC_API_KEY")
        body: dict = {
            "model": s.claude_model or self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        try:
            r = httpx.post(
                _ENDPOINT,
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
                timeout=self.timeout,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"Anthropic request failed: {e}") from e
        parts = r.json().get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
