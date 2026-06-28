"""Headless Claude Code provider — runs `claude -p ... --output-format json` as a
subprocess. Uses the user's Max plan (zero marginal cost) and can optionally attach
LU's own MCP server so the background Claude calls LU tools for extra data.
"""
from __future__ import annotations

import json
import subprocess

from ..config import get_settings
from .base import LLMError, LLMProvider


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
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
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
        return result
