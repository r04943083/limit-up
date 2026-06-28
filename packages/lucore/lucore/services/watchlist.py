"""Watchlist service: CRUD + CSV import. Symbols are normalized and market-tagged."""
from __future__ import annotations

import csv
import io

from pydantic import BaseModel
from sqlalchemy import select

from sqlalchemy import func

from ..data.cache import ensure_stock
from ..db import session_scope
from ..db.models import Snapshot, Stock, Watchlist, WatchlistItem
from ..markets import infer_market
from .research import ResearchBundle

_SYMBOL_HEADERS = {"symbol", "ticker", "code", "代码", "证券代码", "stock"}


def _norm_tags(tags: str | None) -> str | None:
    """Normalize a comma-separated tag string: trim, drop blanks/dups, preserve order."""
    if not tags:
        return None
    seen: dict[str, None] = {}
    for t in tags.split(","):
        t = t.strip()
        if t:
            seen.setdefault(t, None)
    return ",".join(seen) or None


class WatchlistItemOut(BaseModel):
    id: int
    symbol: str
    market: str
    name: str | None = None
    tags: str | None = None
    note: str | None = None
    sort_order: int = 0


class WatchlistOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    sort_order: int = 0
    items: list[WatchlistItemOut] = []


class QuoteRow(BaseModel):
    """One dense watchlist row: identity + last price + change + a mini sparkline.

    Reads from the stored Snapshot (instant). Fields are null when the symbol has not
    been synced yet (user should run "全部更新" first)."""
    item_id: int
    symbol: str
    market: str
    name: str | None = None
    tags: str | None = None
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    currency: str | None = None
    spark: list[float] = []
    synced_at: str | None = None
    sort_order: int = 0


def _item_out(item: WatchlistItem, stock: Stock | None) -> WatchlistItemOut:
    return WatchlistItemOut(
        id=item.id, symbol=item.symbol, market=(stock.market if stock else infer_market(item.symbol).value),
        name=stock.name if stock else None, tags=item.tags, note=item.note,
        sort_order=item.sort_order or 0,
    )


def _sorted_items(wl: Watchlist) -> list[WatchlistItem]:
    return sorted(wl.items, key=lambda it: (it.sort_order or 0, it.id))


def list_watchlists() -> list[WatchlistOut]:
    with session_scope() as s:
        wls = s.execute(
            select(Watchlist).order_by(Watchlist.sort_order, Watchlist.id)
        ).scalars().all()
        out = []
        for wl in wls:
            items = [_item_out(it, s.get(Stock, it.symbol)) for it in _sorted_items(wl)]
            out.append(WatchlistOut(
                id=wl.id, name=wl.name, description=wl.description,
                sort_order=wl.sort_order or 0, items=items,
            ))
        return out


def get_watchlist(watchlist_id: int) -> WatchlistOut | None:
    with session_scope() as s:
        wl = s.get(Watchlist, watchlist_id)
        if wl is None:
            return None
        items = [_item_out(it, s.get(Stock, it.symbol)) for it in _sorted_items(wl)]
        return WatchlistOut(
            id=wl.id, name=wl.name, description=wl.description,
            sort_order=wl.sort_order or 0, items=items,
        )


def create_watchlist(name: str, description: str | None = None) -> WatchlistOut:
    with session_scope() as s:
        next_order = (s.execute(select(func.max(Watchlist.sort_order))).scalar() or 0) + 1
        wl = Watchlist(name=name, description=description, sort_order=next_order)
        s.add(wl)
        s.flush()
        return WatchlistOut(
            id=wl.id, name=wl.name, description=wl.description, sort_order=wl.sort_order, items=[],
        )


def rename_watchlist(watchlist_id: int, name: str, description: str | None = None) -> WatchlistOut | None:
    name = name.strip()
    if not name:
        return None
    with session_scope() as s:
        wl = s.get(Watchlist, watchlist_id)
        if wl is None:
            return None
        wl.name = name
        if description is not None:
            wl.description = description or None
        s.flush()
        return WatchlistOut(
            id=wl.id, name=wl.name, description=wl.description, sort_order=wl.sort_order or 0, items=[],
        )


def delete_watchlist(watchlist_id: int) -> bool:
    with session_scope() as s:
        wl = s.get(Watchlist, watchlist_id)
        if wl is None:
            return False
        s.delete(wl)  # cascade removes items
        return True


def reorder_watchlists(ordered_ids: list[int]) -> bool:
    """Persist group display order. Listed ids first (in given order); others keep trailing."""
    with session_scope() as s:
        for i, wid in enumerate(ordered_ids):
            wl = s.get(Watchlist, wid)
            if wl is not None:
                wl.sort_order = i
        return True


def reorder_items(watchlist_id: int, ordered_item_ids: list[int]) -> bool:
    """Persist within-group item order for the given watchlist."""
    with session_scope() as s:
        for i, iid in enumerate(ordered_item_ids):
            it = s.get(WatchlistItem, iid)
            if it is not None and it.watchlist_id == watchlist_id:
                it.sort_order = i
        return True


def move_item(item_id: int, target_watchlist_id: int) -> bool:
    """Move an item to another group, appended to the end. If the symbol already exists
    in the target group, just drop the source (merge, no duplicates)."""
    with session_scope() as s:
        it = s.get(WatchlistItem, item_id)
        target = s.get(Watchlist, target_watchlist_id)
        if it is None or target is None:
            return False
        if it.watchlist_id == target_watchlist_id:
            return True
        dup = s.execute(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == target_watchlist_id,
                WatchlistItem.symbol == it.symbol,
            )
        ).scalar_one_or_none()
        if dup is not None:
            s.delete(it)
            return True
        next_order = (s.execute(
            select(func.max(WatchlistItem.sort_order)).where(
                WatchlistItem.watchlist_id == target_watchlist_id
            )
        ).scalar() or 0) + 1
        it.watchlist_id = target_watchlist_id
        it.sort_order = next_order
        return True


def update_item(item_id: int, tags: str | None = None, note: str | None = None) -> WatchlistItemOut | None:
    """Update an item's tags and/or note. Pass None to leave a field unchanged."""
    with session_scope() as s:
        it = s.get(WatchlistItem, item_id)
        if it is None:
            return None
        if tags is not None:
            it.tags = _norm_tags(tags)
        if note is not None:
            it.note = note or None
        s.flush()
        return _item_out(it, s.get(Stock, it.symbol))


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
            next_order = (s.execute(
                select(func.max(WatchlistItem.sort_order)).where(
                    WatchlistItem.watchlist_id == watchlist_id
                )
            ).scalar() or 0) + 1
            item = WatchlistItem(
                watchlist_id=watchlist_id, symbol=symbol,
                tags=_norm_tags(tags), note=note, sort_order=next_order,
            )
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


def quotes_for(watchlist_id: int) -> list[QuoteRow]:
    """Dense quote rows for a watchlist, read from stored snapshots (fast, no live fetch)."""
    with session_scope() as s:
        wl = s.get(Watchlist, watchlist_id)
        if wl is None:
            return []
        rows: list[QuoteRow] = []
        for it in _sorted_items(wl):
            stock = s.get(Stock, it.symbol)
            market = stock.market if stock else infer_market(it.symbol).value
            name = stock.name if stock else None
            row = QuoteRow(
                item_id=it.id, symbol=it.symbol, market=market, name=name, tags=it.tags,
                sort_order=it.sort_order or 0,
            )
            snap = s.get(Snapshot, it.symbol)
            if snap and snap.bundle_json:
                try:
                    b = ResearchBundle.model_validate_json(snap.bundle_json)
                    row.price = b.quote.price
                    row.change = b.quote.change
                    row.change_pct = b.quote.change_pct
                    row.currency = b.quote.currency
                    row.name = b.quote.name or name
                    row.spark = b.spark
                    row.synced_at = snap.synced_at.isoformat() if snap.synced_at else None
                except Exception:  # noqa: BLE001 - a bad snapshot shouldn't break the list
                    pass
            rows.append(row)
        return rows


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
