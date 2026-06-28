"""Data sync — one-click "pull latest into the DB" so pages then load instantly.

Live market fetches (quote/fundamentals/news via yfinance) are the slow part of a page
load. Sync fetches them once, persists a snapshot + OHLCV bars, and afterwards the UI
reads from SQLite. Run it on demand (a button) or on a schedule later.
"""
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel
from sqlalchemy import select

from ..db import session_scope
from ..db.models import Holding, Snapshot, WatchlistItem
from .research import build_research_bundle


class SyncResult(BaseModel):
    requested: int
    synced: int
    failed: list[str] = []
    synced_at: dt.datetime


def tracked_symbols() -> list[str]:
    """Every symbol the user follows: watchlist items + portfolio holdings, deduped."""
    with session_scope() as s:
        wl = s.execute(select(WatchlistItem.symbol)).scalars().all()
        hold = s.execute(select(Holding.symbol)).scalars().all()
    seen: dict[str, None] = {}
    for sym in [*wl, *hold]:
        seen.setdefault(sym.upper(), None)
    return list(seen)


# Chart timeframes to pre-warm so the research page renders every period from the DB
# (build_research_bundle already covers 1d). Each entry is (period, interval).
_WARM_BARS = [("5y", "1wk"), ("max", "1mo")]


def sync_symbol(symbol: str, warm: bool = False) -> bool:
    """Force a live refresh of one symbol and persist its snapshot. True on success.

    `warm=True` also fetches weekly/monthly OHLCV so the chart's period switcher is
    instant. We only warm on a *single-symbol* refresh (cheap, user is looking at it);
    the bulk daily sync stays lean — warming every tracked symbol would triple network
    work for hundreds of symbols and is what made "全部更新" slow."""
    sym = symbol.strip().upper()
    try:
        build_research_bundle(sym)
    except Exception:
        return False
    if warm:
        from ..data.router import get_router
        for period, interval in _WARM_BARS:
            try:
                get_router().get_ohlcv(sym, period=period, interval=interval)
            except Exception:  # noqa: BLE001 - a failed timeframe shouldn't fail the symbol
                pass
    return True


# yfinance is network-I/O bound, so fetching symbols concurrently is a big win
# (a few hundred symbols sequentially can take many minutes). Kept modest to be
# polite to the data source and to limit SQLite write contention.
_SYNC_WORKERS = 12


def sync_symbols(symbols: list[str], workers: int = _SYNC_WORKERS, warm: bool = False) -> SyncResult:
    failed: list[str] = []
    synced = 0
    if symbols:
        with ThreadPoolExecutor(max_workers=min(workers, len(symbols))) as pool:
            results = pool.map(lambda s: sync_symbol(s, warm=warm), symbols)
            for sym, ok in zip(symbols, results):
                if ok:
                    synced += 1
                else:
                    failed.append(sym.upper())
    return SyncResult(
        requested=len(symbols), synced=synced, failed=failed,
        synced_at=dt.datetime.now(dt.timezone.utc),
    )


def sync_all() -> SyncResult:
    """Refresh every tracked symbol (watchlist + portfolio)."""
    return sync_symbols(tracked_symbols())


class FreshnessRow(BaseModel):
    symbol: str
    synced_at: dt.datetime | None


def freshness() -> list[FreshnessRow]:
    """Per-symbol last-synced time, newest first — drives the 'data updated at' UI."""
    with session_scope() as s:
        rows = s.execute(select(Snapshot).order_by(Snapshot.synced_at.desc())).scalars().all()
        return [FreshnessRow(symbol=r.symbol, synced_at=r.synced_at) for r in rows]
