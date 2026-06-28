"""Research service: assembles the deterministic *facts bundle* for a symbol.

This bundle is the "facts contract" handed to the LLM — it narrates/scores these facts
but never invents numbers. The same bundle powers the Stock Research page header.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from ..compute.indicators import TechnicalAnalysis, compute_technical
from ..data.base import Fundamentals, NewsItem, Quote
from ..data.router import get_router
from ..markets import infer_market


class ResearchBundle(BaseModel):
    symbol: str
    market: str
    quote: Quote
    fundamentals: Fundamentals
    technical_latest: dict[str, float | None]
    technical_trend: str
    technical_signals: list[str]
    news: list[NewsItem]
    generated_at: dt.datetime


def get_technical(symbol: str, period: str = "1y", interval: str = "1d") -> TechnicalAnalysis:
    bars = get_router().get_ohlcv(symbol, period=period, interval=interval)
    return compute_technical(bars)


def build_research_bundle(symbol: str, news_limit: int = 6) -> ResearchBundle:
    router = get_router()
    quote = router.get_quote(symbol)
    fundamentals = router.get_fundamentals(symbol)
    ta = get_technical(symbol)
    news = router.get_news(symbol, limit=news_limit)
    return ResearchBundle(
        symbol=symbol,
        market=infer_market(symbol).value,
        quote=quote,
        fundamentals=fundamentals,
        technical_latest=ta.latest,
        technical_trend=ta.trend,
        technical_signals=ta.signals,
        news=news,
        generated_at=dt.datetime.now(dt.timezone.utc),
    )
