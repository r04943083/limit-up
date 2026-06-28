"""Data sync — one-click "pull latest into the DB" so pages then load instantly.

Live market fetches (quote/fundamentals/news via yfinance) are the slow part of a page
load. Sync fetches them once, persists a snapshot + OHLCV bars, and afterwards the UI
reads from SQLite. Run it on demand (a button) or on a schedule later.
"""
from __future__ import annotations

import datetime as dt

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


def sync_symbol(symbol: str) -> bool:
    """Force a live refresh of one symbol and persist its snapshot. True on success."""
    try:
        build_research_bundle(symbol.strip().upper())
        return True
    except Exception:
        return False


def sync_symbols(symbols: list[str]) -> SyncResult:
    failed: list[str] = []
    synced = 0
    for sym in symbols:
        if sync_symbol(sym):
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
