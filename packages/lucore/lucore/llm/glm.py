"""GLM-4.6 provider (Zhipu / Z.AI, OpenAI-compatible). Optional, paid, cheap.

Off by default; enable with LU_LLM_PROVIDER=glm and LU_GLM_API_KEY=...
"""
from __future__ import annotations

import httpx

from ..config import get_settings
from .base import LLMError, LLMProvider

_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


class GLMProvider(LLMProvider):
    name = "glm"

    def __init__(self, model: str = "glm-4.6", timeout: int = 120) -> None:
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        key = get_settings().glm_api_key
        if not key:
            raise LLMError("GLM provider requires LU_GLM_API_KEY")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            r = httpx.post(
                _ENDPOINT,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": self.model, "messages": messages},
                timeout=self.timeout,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"GLM request failed: {e}") from e
        return r.json()["choices"][0]["message"]["content"]
