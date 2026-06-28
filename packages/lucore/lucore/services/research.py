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
from ..db import session_scope
from ..db.models import Snapshot
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
    spark: list[float] = []  # last ~40 daily closes, for watchlist mini-charts
    generated_at: dt.datetime


def get_technical(symbol: str, period: str = "1y", interval: str = "1d") -> TechnicalAnalysis:
    bars = get_router().get_ohlcv(symbol, period=period, interval=interval)
    return compute_technical(bars)


def build_research_bundle(symbol: str, news_limit: int = 6) -> ResearchBundle:
    """Always fetch live and assemble fresh facts. Also persists a snapshot so later
    reads can load from the DB instantly (see `get_research`)."""
    router = get_router()
    quote = router.get_quote(symbol)
    fundamentals = router.get_fundamentals(symbol)
    bars = router.get_ohlcv(symbol, period="1y", interval="1d")
    ta = compute_technical(bars)
    news = router.get_news(symbol, limit=news_limit)
    spark = [b.close for b in bars[-40:] if b.close is not None]
    bundle = ResearchBundle(
        symbol=symbol,
        market=infer_market(symbol).value,
        quote=quote,
        fundamentals=fundamentals,
        technical_latest=ta.latest,
        technical_trend=ta.trend,
        technical_signals=ta.signals,
        news=news,
        spark=spark,
        generated_at=dt.datetime.now(dt.timezone.utc),
    )
    save_snapshot(bundle)
    return bundle


def save_snapshot(bundle: ResearchBundle) -> None:
    """Persist the full research bundle for fast cached reads."""
    now = dt.datetime.now(dt.timezone.utc)
    with session_scope() as s:
        snap = s.get(Snapshot, bundle.symbol)
        if snap is None:
            snap = Snapshot(symbol=bundle.symbol)
            s.add(snap)
        snap.bundle_json = bundle.model_dump_json()
        snap.synced_at = now


def load_snapshot(symbol: str) -> ResearchBundle | None:
    with session_scope() as s:
        snap = s.get(Snapshot, symbol)
        if snap is None or not snap.bundle_json:
            return None
        return ResearchBundle.model_validate_json(snap.bundle_json)


def get_research(symbol: str, *, cached: bool = True, news_limit: int = 6) -> ResearchBundle:
    """Cached-first read for the UI: return the stored snapshot if present (fast),
    otherwise fetch live and persist it. Pass cached=False to force a live refresh."""
    if cached:
        snap = load_snapshot(symbol)
        if snap is not None:
            return snap
    return build_research_bundle(symbol, news_limit=news_limit)


def snapshot_synced_at(symbol: str) -> dt.datetime | None:
    with session_scope() as s:
        snap = s.get(Snapshot, symbol)
        return snap.synced_at if snap else None
