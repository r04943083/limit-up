"""SQLite caching for market data. Daily bars are immutable history → cache forever;
the router decides when to refresh based on the latest cached date.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..db import session_scope
from ..db.models import PriceBar, Stock
from ..markets import infer_market
from .base import Bar


def ensure_stock(symbol: str, name: str | None = None, **fields) -> None:
    market = infer_market(symbol)
    with session_scope() as s:
        stock = s.get(Stock, symbol)
        if stock is None:
            s.add(Stock(symbol=symbol, market=market.value, name=name, **fields))
        else:
            if name and not stock.name:
                stock.name = name
            for k, v in fields.items():
                if v and not getattr(stock, k, None):
                    setattr(stock, k, v)


def read_bars(symbol: str, interval: str = "1d") -> list[Bar]:
    with session_scope() as s:
        rows = s.execute(
            select(PriceBar)
            .where(PriceBar.symbol == symbol, PriceBar.interval == interval)
            .order_by(PriceBar.date)
        ).scalars().all()
        return [
            Bar(date=r.date, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume)
            for r in rows
        ]


def latest_cached_date(symbol: str, interval: str = "1d") -> dt.date | None:
    with session_scope() as s:
        return s.execute(
            select(PriceBar.date)
            .where(PriceBar.symbol == symbol, PriceBar.interval == interval)
            .order_by(PriceBar.date.desc())
            .limit(1)
        ).scalar_one_or_none()


def write_bars(symbol: str, interval: str, bars: list[Bar]) -> int:
    """Insert bars idempotently (symbol+interval+date). Lets SQLite skip duplicates via
    ON CONFLICT DO NOTHING — no full-table date scan, scales to long histories."""
    if not bars:
        return 0
    # Deduplicate within the incoming batch (same date appearing twice would still
    # conflict against the first inserted row in this statement).
    seen: dict[dt.date, Bar] = {}
    for b in bars:
        seen[b.date] = b
    payload = [
        {
            "symbol": symbol, "interval": interval, "date": b.date,
            "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume,
        }
        for b in seen.values()
    ]
    with session_scope() as s:
        stmt = sqlite_insert(PriceBar).values(payload).on_conflict_do_nothing(
            index_elements=["symbol", "interval", "date"]
        )
        result = s.execute(stmt)
        return result.rowcount or 0
