"""Watchlist service: CRUD + CSV import. Symbols are normalized and market-tagged."""
from __future__ import annotations

import csv
import io

from pydantic import BaseModel
from sqlalchemy import select

from ..data.cache import ensure_stock
from ..db import session_scope
from ..db.models import Stock, Watchlist, WatchlistItem
from ..markets import infer_market

_SYMBOL_HEADERS = {"symbol", "ticker", "code", "代码", "证券代码", "stock"}


class WatchlistItemOut(BaseModel):
    id: int
    symbol: str
    market: str
    name: str | None = None
    tags: str | None = None
    note: str | None = None


class WatchlistOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    items: list[WatchlistItemOut] = []


def _item_out(item: WatchlistItem, stock: Stock | None) -> WatchlistItemOut:
    return WatchlistItemOut(
        id=item.id, symbol=item.symbol, market=(stock.market if stock else infer_market(item.symbol).value),
        name=stock.name if stock else None, tags=item.tags, note=item.note,
    )


def list_watchlists() -> list[WatchlistOut]:
    with session_scope() as s:
        wls = s.execute(select(Watchlist).order_by(Watchlist.id)).scalars().all()
        out = []
        for wl in wls:
            items = [_item_out(it, s.get(Stock, it.symbol)) for it in wl.items]
            out.append(WatchlistOut(id=wl.id, name=wl.name, description=wl.description, items=items))
        return out


def get_watchlist(watchlist_id: int) -> WatchlistOut | None:
    with session_scope() as s:
        wl = s.get(Watchlist, watchlist_id)
        if wl is None:
            return None
        items = [_item_out(it, s.get(Stock, it.symbol)) for it in wl.items]
        return WatchlistOut(id=wl.id, name=wl.name, description=wl.description, items=items)


def create_watchlist(name: str, description: str | None = None) -> WatchlistOut:
    with session_scope() as s:
        wl = Watchlist(name=name, description=description)
        s.add(wl)
        s.flush()
        return WatchlistOut(id=wl.id, name=wl.name, description=wl.description, items=[])


def ensure_default_watchlist() -> int:
    with session_scope() as s:
        wl = s.execute(select(Watchlist).order_by(Watchlist.id).limit(1)).scalar_one_or_none()
        if wl:
            return wl.id
        wl = Watchlist(name="My Watchlist")
        s.add(wl)
        s.flush()
        return wl.id


def add_item(
    watchlist_id: int, symbol: str, tags: str | None = None, note: str | None = None
) -> WatchlistItemOut | None:
    symbol = symbol.strip().upper()
    if not symbol:
        return None
    ensure_stock(symbol)
    with session_scope() as s:
        exists = s.execute(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.symbol == symbol
            )
        ).scalar_one_or_none()
        if exists:
            item = exists
        else:
            item = WatchlistItem(watchlist_id=watchlist_id, symbol=symbol, tags=tags, note=note)
            s.add(item)
            s.flush()
        return _item_out(item, s.get(Stock, symbol))


def remove_item(item_id: int) -> bool:
    with session_scope() as s:
        item = s.get(WatchlistItem, item_id)
        if item is None:
            return False
        s.delete(item)
        return True


def import_csv(watchlist_id: int, csv_text: str) -> int:
    """Extract symbols from a CSV (broker export or simple list) and add them. Returns count added."""
    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if r]
    if not rows:
        return 0
    header = [h.strip().lower() for h in rows[0]]
    col = next((i for i, h in enumerate(header) if h in _SYMBOL_HEADERS), None)
    data_rows = rows[1:] if col is not None else rows
    if col is None:
        col = 0  # no header -> first column is the symbol
    added = 0
    for r in data_rows:
        if col < len(r):
            sym = r[col].strip().upper()
            if sym and add_item(watchlist_id, sym):
                added += 1
    return added
