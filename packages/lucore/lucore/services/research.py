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


def _fundamentals_throttled(f: Fundamentals) -> bool:
    """The rate-limit signature: yfinance's `.info` came back empty, so market cap AND
    trailing PE AND ROE are *all* absent at once — a healthy fetch of a real equity never
    is. We deliberately require all three (not just any None) so that a single field going
    None for a legitimate reason — a dividend cut clearing `dividend_yield`, a swing to a
    loss clearing `pe_ttm`, dropped analyst coverage clearing `target_mean` — is NOT mistaken
    for a throttle and is allowed to overwrite the stale cached value."""
    return f.market_cap is None and f.pe_ttm is None and f.roe is None


def save_snapshot(bundle: ResearchBundle) -> None:
    """Persist the full research bundle for fast cached reads.

    Anti-clobber guard: yfinance routinely rate-limits the fundamentals endpoint during
    bulk syncs — the quote/bars come through but `.info` returns empty. Writing that as-is
    would overwrite a perfectly good prior snapshot with empty fundamentals (the exact bug
    that left MSFT et al. with blank PE/ROE/name). So when the incoming fundamentals are
    empty but the stored ones are populated, we keep the *good* fundamentals and only
    refresh the volatile parts (quote / technicals / news / spark)."""
    now = dt.datetime.now(dt.timezone.utc)
    with session_scope() as s:
        snap = s.get(Snapshot, bundle.symbol)
        if snap is None:
            snap = Snapshot(symbol=bundle.symbol)
            s.add(snap)
        elif snap.bundle_json and (
            _fundamentals_throttled(bundle.fundamentals) or bundle.quote.price is None
        ):
            # Only pay the extra read/parse when the fresh fetch looks degraded (throttled
            # fundamentals or a priceless quote); a healthy fetch skips this entirely.
            try:
                prev = ResearchBundle.model_validate_json(snap.bundle_json)
            except Exception:  # noqa: BLE001
                prev = None
            if prev is not None:
                update: dict = {}
                # Throttled fundamentals → keep the whole prior good block rather than blank
                # it. (Whole-block, not field-level: when the throttle signature fires we know
                # the fetch is degraded, so we don't risk resurrecting a legitimately-cleared field.)
                if _fundamentals_throttled(bundle.fundamentals) and not _fundamentals_throttled(prev.fundamentals):
                    update["fundamentals"] = prev.fundamentals
                # A quote that came back without a price (throttled) must not blank the
                # last-good price/change either.
                if bundle.quote.price is None and prev.quote.price is not None:
                    update["quote"] = prev.quote
                if update:
                    bundle = bundle.model_copy(update=update)
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
