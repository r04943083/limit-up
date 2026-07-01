"""Headless Claude Code provider — runs `claude -p ... --output-format json` as a
subprocess. Uses the user's Max plan (zero marginal cost) and can optionally attach
LU's own MCP server so the background Claude calls LU tools for extra data.
"""
from __future__ import annotations

import json
import subprocess

from ..config import get_settings
from .base import LLMError, LLMProvider
from .concurrency import LLMBusyError, llm_slot


class ClaudeCodeProvider(LLMProvider):
    name = "claude_code"

    def __init__(self, timeout: int = 180, mcp_config: str | None = None) -> None:
        self.timeout = timeout
        self.mcp_config = mcp_config

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        s = get_settings()
        cmd = [s.claude_bin, "-p", prompt, "--output-format", "json"]
        if system:
            cmd += ["--append-system-prompt", system]
        if s.claude_model:
            cmd += ["--model", s.claude_model]
        if self.mcp_config:
            cmd += ["--mcp-config", self.mcp_config]
        try:
            # Throttle concurrent subprocesses to a safe width (shared Max-plan quota).
            # Bound the queue wait by the same timeout so a burst can't hang a caller forever.
            with llm_slot(timeout=self.timeout):
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=self.timeout
                )
        except LLMBusyError as e:
            raise LLMError(str(e)) from e
        except FileNotFoundError as e:
            raise LLMError(
                f"`{s.claude_bin}` not found — install Claude Code or set LU_CLAUDE_BIN"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"claude -p timed out after {self.timeout}s") from e

        if proc.returncode != 0:
            raise LLMError(f"claude -p exited {proc.returncode}: {proc.stderr[:300]}")

        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise LLMError(f"could not parse claude -p envelope: {proc.stdout[:300]!r}") from e

        if envelope.get("is_error"):
            raise LLMError(f"claude -p reported error: {envelope.get('result')!r}")
        result = envelope.get("result")
        if not isinstance(result, str):
            raise LLMError(f"unexpected claude -p result type: {type(result)}")
        self.last_meta = _usage_from_envelope(envelope, s.claude_model)
        return result


def _usage_from_envelope(envelope: dict, model: str | None) -> dict:
    """Extract token/cost metadata from the `claude -p --output-format json` envelope."""
    usage = envelope.get("usage") or {}
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    cache_create = int(usage.get("cache_creation_input_tokens") or 0)
    # Prefer the model the run actually used (modelUsage keys) over the configured one.
    model_usage = envelope.get("modelUsage") or {}
    used_model = next(iter(model_usage), None) or model
    return {
        "provider": "claude_code",
        "model": used_model,
        "input_tokens": inp,
        "output_tokens": out,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_create,
        "total_tokens": inp + out + cache_read + cache_create,
        "cost_usd": float(envelope.get("total_cost_usd") or 0.0),
        "duration_ms": int(envelope.get("duration_ms") or 0),
        "num_turns": int(envelope.get("num_turns") or 0),
    }
