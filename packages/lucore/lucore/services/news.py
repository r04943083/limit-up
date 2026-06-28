"""News sentiment service — aggregate recent headlines (deterministic fetch) and have
the AI brain classify impact/sentiment + extract bull/bear points (reasoning only).

Write-back lands in `analyses` with kind="news", idempotent per day, labeled opinion.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..data.base import NewsItem
from ..data.router import get_router
from ..db import session_scope
from ..db.models import Analysis
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage

SYSTEM_PROMPT = (
    "You are LU's news/sentiment analyst. You are given a symbol and a list of recent "
    "headlines (titles + publishers). Judge the likely market impact and sentiment of the "
    "news flow as a whole, and extract the bullish and bearish threads. Reason only over the "
    "given headlines — do not invent events or numbers. Respond with ONLY one JSON object."
)

OUTPUT_SPEC = {
    "overall": "one of: bullish | neutral | bearish",
    "impact": "one of: high | medium | low (how market-moving the flow is)",
    "summary": "2-4 sentences summarizing the news narrative and its read-through",
    "bull_points": ["short bullets drawn from the headlines"],
    "bear_points": ["short bullets drawn from the headlines"],
}


class NewsSentiment(BaseModel):
    overall: str = "neutral"
    impact: str = "low"
    summary: str = ""
    bull_points: list[str] = []
    bear_points: list[str] = []
    headlines_assessed: int = 0


class SavedNewsAnalysis(BaseModel):
    symbol: str
    provider: str
    created_at: dt.datetime
    headlines: list[NewsItem] = Field(default_factory=list)
    result: NewsSentiment


def _build_prompt(symbol: str, news: list[NewsItem]) -> str:
    headlines = [{"title": n.title, "publisher": n.publisher} for n in news]
    return (
        f"Symbol: {symbol}\nRecent headlines (most recent first):\n"
        f"{json.dumps(headlines, indent=2, ensure_ascii=False)}\n\n"
        f"Return ONLY JSON with exactly these keys:\n{json.dumps(OUTPUT_SPEC, indent=2)}"
    )


def analyze_news(
    symbol: str, *, limit: int = 12, provider: LLMProvider | None = None
) -> SavedNewsAnalysis:
    symbol = symbol.upper()
    news = get_router().get_news(symbol, limit=limit)
    provider = provider or get_provider()

    if not news:
        result = NewsSentiment(summary="近期没有可用的新闻。", headlines_assessed=0)
    else:
        raw = provider.generate_json(_build_prompt(symbol, news), system=with_chinese(SYSTEM_PROMPT))
        usage.record(provider, "news", symbol)
        result = NewsSentiment.model_validate(raw)
        result.headlines_assessed = len(news)

    return _persist(symbol, news, result, provider.name)


def _persist(symbol: str, news: list[NewsItem], result: NewsSentiment, provider: str) -> SavedNewsAnalysis:
    idem = dt.date.today().isoformat()
    with session_scope() as s:
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == symbol, Analysis.kind == "news", Analysis.idempotency_key == idem
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=symbol, kind="news", idempotency_key=idem)
            s.add(existing)
        existing.summary = result.summary
        existing.structured_json = json.dumps({
            "result": result.model_dump(),
            "headlines": [n.model_dump(mode="json") for n in news],
        })
        existing.provider = provider
        s.flush()
        return SavedNewsAnalysis(
            symbol=symbol, provider=provider,
            created_at=existing.created_at or dt.datetime.now(dt.timezone.utc),
            headlines=news, result=result,
        )


def latest_news_analysis(symbol: str) -> SavedNewsAnalysis | None:
    symbol = symbol.upper()
    with session_scope() as s:
        row = s.execute(
            select(Analysis)
            .where(Analysis.symbol == symbol, Analysis.kind == "news")
            .order_by(Analysis.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        blob = json.loads(row.structured_json)
        return SavedNewsAnalysis(
            symbol=row.symbol, provider=row.provider, created_at=row.created_at,
            headlines=[NewsItem.model_validate(h) for h in blob.get("headlines", [])],
            result=NewsSentiment.model_validate(blob.get("result", {})),
        )
