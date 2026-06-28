"""Pluggable LLM provider interface.

Default = claude_code (headless `claude -p`, zero marginal cost on a Max plan).
Optional = glm, anthropic (paid). The provider only reasons over facts LU computed;
it never produces the numbers themselves.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from ..config import get_settings


class LLMError(RuntimeError):
    pass


# Shared language directive appended to every system prompt: AI narration in
# Simplified Chinese, finance jargon kept in English, JSON keys untouched.
LANG_DIRECTIVE = (
    "请用简体中文撰写所有叙述性字段的值(例如 summary、thesis、bull_case、bear_case、"
    "risks、catalysts、strengths、concerns、suggestions、headline、impact 等)。"
    "专有金融术语保留英文(如 P/E、PEG、RSI、MACD、ROE、EV/EBITDA、Strong Buy/Buy/Hold/Sell)。"
    "JSON 的键名(keys)和枚举类的取值保持英文不变,只把面向人阅读的文本翻译成中文。"
)


def with_chinese(system: str) -> str:
    """Append the Chinese-narration directive to a system prompt."""
    return f"{system}\n\n{LANG_DIRECTIVE}"


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (tolerant of ``` fences / prose)."""
    if not text:
        raise LLMError("empty LLM response")
    t = text.strip()
    # Strip markdown code fences if present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL)
    if fence:
        t = fence.group(1)
    # Otherwise grab the outermost {...}.
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMError(f"no JSON object in LLM response: {text[:200]!r}")
    blob = t[start : end + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON from LLM: {e}") from e


class LLMProvider(ABC):
    name: str = "base"
    # Populated by complete() with the most recent call's usage/cost metadata
    # (tokens, cost_usd, duration_ms, num_turns, model). None until a call runs.
    last_meta: dict | None = None

    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's raw text response."""

    def generate_json(self, prompt: str, *, system: str | None = None) -> dict:
        return extract_json(self.complete(prompt, system=system))


def get_provider(name: str | None = None) -> LLMProvider:
    name = name or get_settings().llm_provider
    if name == "claude_code":
        from .claude_code import ClaudeCodeProvider

        return ClaudeCodeProvider()
    if name == "glm":
        from .glm import GLMProvider

        return GLMProvider()
    if name == "anthropic":
        from .anthropic_api import AnthropicProvider

        return AnthropicProvider()
    raise LLMError(f"unknown LLM provider: {name}")
