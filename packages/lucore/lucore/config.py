"""Central configuration for LU. Loaded once, from environment / .env file.

Personal local tool: defaults are chosen so the app runs with zero config and
zero AI cost (LLM provider defaults to headless `claude -p`).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = three levels up from this file: packages/lucore/lucore/config.py -> repo/
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LU_",
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Storage ---
    data_dir: Path = Field(default=DEFAULT_DATA_DIR)
    db_filename: str = Field(default="lu.db")

    # --- LLM provider ---
    # "claude_code" (default, zero-cost, uses Max plan via `claude -p`),
    # "glm" (paid, cheap), "anthropic" (paid, highest quality).
    llm_provider: str = Field(default="claude_code")
    claude_bin: str = Field(default="claude")
    claude_model: str | None = Field(default=None)  # None = Claude Code default
    glm_api_key: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    # Cap concurrent LLM subprocesses. Every `claude -p` forks a heavy Claude Code process
    # sharing one Max-plan quota; without a cap, a burst of concurrent AI requests fork-bombs
    # the host and trips rate limits. Requests beyond the cap queue (fair) rather than fail.
    llm_max_concurrency: int = Field(default=2, ge=1)

    # --- Data sources ---
    # Comma-free; toggled individually. yfinance needs no key.
    sec_user_agent: str = Field(default="limit-up LU research willu.star@gmail.com")
    finnhub_api_key: str | None = Field(default=None)

    # --- Markets enabled (US always on; HK/A-share via akshare+futu) ---
    enable_hk: bool = Field(default=True)
    enable_cn: bool = Field(default=True)

    # --- Scheduler (in-process APScheduler) ---
    enable_scheduler: bool = Field(default=True)
    briefing_hour: int = Field(default=8)     # local hour to auto-sync + write the daily briefing
    briefing_minute: int = Field(default=30)

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "parquet").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "exports").mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
