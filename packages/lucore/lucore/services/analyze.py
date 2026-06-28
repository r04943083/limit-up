"""Analyze service — the dual-brain write-back loop.

build facts bundle (deterministic) -> LLM reasons (claude -p) -> validate -> persist to `analyses`.
The LLM is told to treat the provided numbers as ground truth and never invent figures.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import session_scope
from ..db.models import Analysis
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage
from .research import ResearchBundle, build_research_bundle

SYSTEM_PROMPT = (
    "You are LU's equity analyst. You are given FACTS computed by LU's deterministic engine "
    "(price, fundamentals, technical indicators, analyst consensus, recent news). Treat every "
    "number as ground truth — never invent or recompute figures. Reason over the facts and return "
    "a concise, balanced view. Respond with ONLY a single JSON object, no prose, no code fences."
)

OUTPUT_SPEC = {
    "summary": "2-4 sentence plain-English summary of the setup",
    "recommendation": "one of: Strong Buy | Buy | Hold | Sell | Strong Sell",
    "score": "number 0-10 = your conviction this is attractive to buy now",
    "bull_case": "the strongest bullish argument, grounded in the facts",
    "bear_case": "the strongest bearish argument, grounded in the facts",
    "risks": ["short risk bullets"],
    "catalysts": ["short catalyst bullets"],
    "target_price": "number or null (anchor on provided analyst targets + valuation)",
    "time_horizon": "e.g. '6-12 months' or null",
}


class AnalysisResult(BaseModel):
    summary: str
    recommendation: str
    score: float = Field(ge=0, le=10)
    bull_case: str = ""
    bear_case: str = ""
    risks: list[str] = []
    catalysts: list[str] = []
    target_price: float | None = None
    time_horizon: str | None = None


class SavedAnalysis(BaseModel):
    id: int
    symbol: str
    kind: str
    provider: str
    created_at: dt.datetime
    result: AnalysisResult


def _facts(bundle: ResearchBundle) -> dict:
    """Compact, non-null facts dict for the prompt (keeps it small)."""
    f = bundle.fundamentals
    fund = {k: v for k, v in f.model_dump().items() if v is not None and k not in ("symbol", "market")}
    return {
        "symbol": bundle.symbol,
        "market": bundle.market,
        "price": bundle.quote.price,
        "currency": bundle.quote.currency,
        "fundamentals": fund,
        "technical": {
            "trend": bundle.technical_trend,
            "signals": bundle.technical_signals,
            "rsi14": bundle.technical_latest.get("rsi14"),
            "sma50": bundle.technical_latest.get("sma50"),
            "sma200": bundle.technical_latest.get("sma200"),
        },
        "recent_news": [n.title for n in bundle.news][:6],
    }


def build_prompt(bundle: ResearchBundle) -> str:
    return (
        f"Analyze {bundle.symbol}. FACTS (ground truth):\n"
        f"{json.dumps(_facts(bundle), indent=2, default=str)}\n\n"
        f"Return ONLY JSON with exactly these keys:\n"
        f"{json.dumps(OUTPUT_SPEC, indent=2)}"
    )


def persist_analysis(symbol: str, result: AnalysisResult, provider: str = "claude_code") -> SavedAnalysis:
    """Write-back: persist a validated AI opinion. Used by the web path AND the MCP
    `save_analysis` tool (so external Claude can save its own reasoning). Idempotent per day."""
    symbol = symbol.upper()
    idem = dt.date.today().isoformat()
    with session_scope() as s:
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == symbol,
                Analysis.kind == "research",
                Analysis.idempotency_key == idem,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=symbol, kind="research", idempotency_key=idem)
            s.add(existing)
        existing.summary = result.summary
        existing.structured_json = result.model_dump_json()
        existing.provider = provider
        s.flush()
        return SavedAnalysis(
            id=existing.id, symbol=symbol, kind="research", provider=provider,
            created_at=existing.created_at or dt.datetime.now(dt.timezone.utc), result=result,
        )


def analyze_stock(
    symbol: str, *, provider: LLMProvider | None = None, persona_system: str | None = None
) -> SavedAnalysis:
    bundle = build_research_bundle(symbol)
    provider = provider or get_provider()
    system = with_chinese(persona_system or SYSTEM_PROMPT)

    raw = provider.generate_json(build_prompt(bundle), system=system)
    usage.record(provider, "research", symbol)
    result = AnalysisResult.model_validate(raw)
    return persist_analysis(symbol, result, provider=provider.name)


def latest_analysis(symbol: str, kind: str = "research") -> SavedAnalysis | None:
    with session_scope() as s:
        row = s.execute(
            select(Analysis)
            .where(Analysis.symbol == symbol, Analysis.kind == kind)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        return SavedAnalysis(
            id=row.id, symbol=row.symbol, kind=row.kind, provider=row.provider,
            created_at=row.created_at, result=AnalysisResult.model_validate_json(row.structured_json),
        )
