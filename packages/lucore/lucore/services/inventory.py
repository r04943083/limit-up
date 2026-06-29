"""Data inventory — "how much have we actually downloaded?".

Answers the user's question: how many US / A-share / HK stocks do we hold locally, and
how complete is each (price bars, research snapshot, financial statements, profile)?
Pure reads over the local DB; no network. Drives the 「数据」 page.
"""
from __future__ import annotations

import datetime as dt
import os

from pydantic import BaseModel
from sqlalchemy import distinct, func, select

from ..config import get_settings
from ..db import session_scope
from ..db.models import (
    FinancialsCache,
    PriceBar,
    ProfileCache,
    Snapshot,
    Stock,
)

# Friendly market labels (the UI shows these; keys match Stock.market).
MARKET_LABELS = {"US": "美股", "CN": "A股", "HK": "港股"}


class MarketInventory(BaseModel):
    market: str
    label: str
    stocks: int = 0          # rows in `stocks`
    with_bars: int = 0       # have ≥1 cached daily/any-interval bar
    with_snapshot: int = 0   # have a research snapshot (quote+fundamentals+news)
    with_financials: int = 0 # have cached statements
    with_profile: int = 0    # have cached company profile
    bars: int = 0            # total cached price bars for the market


class Inventory(BaseModel):
    markets: list[MarketInventory]
    total_stocks: int = 0
    total_bars: int = 0
    total_snapshots: int = 0
    db_bytes: int | None = None
    last_synced_at: dt.datetime | None = None


def _count_distinct_symbols_by_market(s, table) -> dict[str, int]:
    """{market: # of distinct symbols in `table` that join to a stock}."""
    rows = s.execute(
        select(Stock.market, func.count(distinct(table.symbol)))
        .select_from(table)
        .join(Stock, Stock.symbol == table.symbol)
        .group_by(Stock.market)
    ).all()
    return {m: n for m, n in rows}


def get_inventory() -> Inventory:
    with session_scope() as s:
        stock_counts = dict(
            s.execute(select(Stock.market, func.count()).group_by(Stock.market)).all()
        )
        bar_counts = dict(
            s.execute(
                select(Stock.market, func.count())
                .select_from(PriceBar)
                .join(Stock, Stock.symbol == PriceBar.symbol)
                .group_by(Stock.market)
            ).all()
        )
        with_bars = _count_distinct_symbols_by_market(s, PriceBar)
        with_snap = _count_distinct_symbols_by_market(s, Snapshot)
        with_fin = _count_distinct_symbols_by_market(s, FinancialsCache)
        with_prof = _count_distinct_symbols_by_market(s, ProfileCache)
        last_sync = s.execute(select(func.max(Snapshot.synced_at))).scalar()
        total_snapshots = s.execute(select(func.count()).select_from(Snapshot)).scalar() or 0

    markets: list[MarketInventory] = []
    for m in sorted(stock_counts, key=lambda k: (k not in MARKET_LABELS, k)):
        markets.append(MarketInventory(
            market=m, label=MARKET_LABELS.get(m, m),
            stocks=stock_counts.get(m, 0),
            with_bars=with_bars.get(m, 0),
            with_snapshot=with_snap.get(m, 0),
            with_financials=with_fin.get(m, 0),
            with_profile=with_prof.get(m, 0),
            bars=bar_counts.get(m, 0),
        ))

    db_bytes: int | None = None
    try:
        db_bytes = os.path.getsize(get_settings().db_path)
    except OSError:
        db_bytes = None

    return Inventory(
        markets=markets,
        total_stocks=sum(stock_counts.values()),
        total_bars=sum(bar_counts.values()),
        total_snapshots=total_snapshots,
        db_bytes=db_bytes,
        last_synced_at=last_sync,
    )
