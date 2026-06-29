"""Seed the screener universe from index constituents.

Two phases, kept separate so the API can answer fast:

* ``seed_indices(keys)`` — fetch constituent lists and upsert Stock rows (symbol / market /
  name). A few network calls; quick. Afterwards the symbols appear in search + inventory.
* snapshot fill — fetch a research snapshot for symbols that don't have one yet. This is the
  slow part (one yfinance round-trip per symbol), so the API runs it on a background thread
  and reports progress via ``seed_progress``.
"""
from __future__ import annotations

import datetime as dt
import threading

from pydantic import BaseModel
from sqlalchemy import select

from ..data.universe import INDEX_BY_KEY, constituents
from ..db import session_scope
from ..db.models import Snapshot, Stock


class IndexSeed(BaseModel):
    key: str
    label: str
    market: str
    fetched: int


class SeedResult(BaseModel):
    indices: list[IndexSeed]
    total_fetched: int
    added: int           # newly inserted Stock rows
    universe_size: int   # total Stock rows after seeding


def seed_indices(keys: list[str]) -> SeedResult:
    """Fetch members of each index and upsert Stock rows. Dedups across indices (a symbol in
    both 沪深300 and 上证50 is one row). Never overwrites an existing non-null name with null."""
    seen: dict[str, tuple[str, str | None]] = {}  # symbol -> (market, name)
    fetched: dict[str, int] = {}
    for key in keys:
        idef = INDEX_BY_KEY.get(key)
        if not idef:
            continue
        rows = constituents(key)
        fetched[key] = len(rows)
        for sym, name in rows:
            cur = seen.get(sym)
            if cur is None or (cur[1] is None and name):
                seen[sym] = (idef.market, name)

    added = 0
    with session_scope() as s:
        for sym, (market, name) in seen.items():
            row = s.get(Stock, sym)
            if row is None:
                s.add(Stock(symbol=sym, market=market, name=name))
                added += 1
            elif name and not row.name:
                row.name = name
        universe_size = len(s.execute(select(Stock.symbol)).scalars().all())

    indices = [
        IndexSeed(key=k, label=INDEX_BY_KEY[k].label, market=INDEX_BY_KEY[k].market, fetched=fetched.get(k, 0))
        for k in keys if k in INDEX_BY_KEY
    ]
    return SeedResult(
        indices=indices,
        total_fetched=sum(fetched.values()),
        added=added,
        universe_size=universe_size,
    )


def symbols_missing_snapshot() -> list[str]:
    """Universe symbols that have no cached snapshot yet (the fill targets)."""
    with session_scope() as s:
        stocks = set(s.execute(select(Stock.symbol)).scalars().all())
        snapped = set(s.execute(select(Snapshot.symbol)).scalars().all())
    return sorted(stocks - snapped)


def symbols_missing_financials() -> list[str]:
    """Universe symbols that have no cached financial statements yet."""
    from ..db.models import FinancialsCache

    with session_scope() as s:
        stocks = set(s.execute(select(Stock.symbol)).scalars().all())
        have = set(s.execute(select(FinancialsCache.symbol)).scalars().all())
    return sorted(stocks - have)


# --- Background fills --------------------------------------------------------
# A personal single-process API: daemon threads fill data while the user keeps browsing,
# with progress polled by the /screener page. Two independent jobs (snapshots, financials);
# each runs at most one at a time.
def _new_progress() -> dict:
    return {"running": False, "done": 0, "total": 0, "failed": 0,
            "started_at": None, "finished_at": None}


_progress: dict[str, dict] = {"snapshot": _new_progress(), "financials": _new_progress()}
_lock = threading.Lock()


def seed_progress(kind: str = "snapshot") -> dict:
    with _lock:
        return dict(_progress[kind])


def _run_fill(kind: str, symbols: list[str], worker) -> None:  # noqa: ANN001
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .sync import _SYNC_WORKERS

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with _lock:
        _progress[kind] = {"running": True, "done": 0, "total": len(symbols),
                           "failed": 0, "started_at": now, "finished_at": None}
    try:
        if symbols:
            with ThreadPoolExecutor(max_workers=min(_SYNC_WORKERS, len(symbols))) as pool:
                futs = [pool.submit(worker, sym) for sym in symbols]
                for fut in as_completed(futs):
                    try:
                        ok = bool(fut.result())
                    except Exception:  # noqa: BLE001
                        ok = False
                    with _lock:
                        _progress[kind]["done"] += 1
                        if not ok:
                            _progress[kind]["failed"] += 1
    finally:
        with _lock:
            _progress[kind]["running"] = False
            _progress[kind]["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()


def start_snapshot_fill(only_missing: bool = True) -> dict:
    """Kick the background snapshot fill (no-op if one is already running). Returns progress."""
    with _lock:
        if _progress["snapshot"]["running"]:
            return dict(_progress["snapshot"])
    if only_missing:
        symbols = symbols_missing_snapshot()
    else:
        with session_scope() as s:
            symbols = list(s.execute(select(Stock.symbol)).scalars().all())

    from .sync import sync_symbol

    threading.Thread(target=_run_fill, args=("snapshot", symbols, sync_symbol), daemon=True).start()
    return seed_progress("snapshot")


def start_financials_fill(only_missing: bool = True) -> dict:
    """Kick the background financials + profile fill so the valuation band / percentile work
    for the whole pool. Heavy (one extra yfinance round-trip per symbol) — runs in the
    background. No-op if one is already running."""
    with _lock:
        if _progress["financials"]["running"]:
            return dict(_progress["financials"])
    if only_missing:
        symbols = symbols_missing_financials()
    else:
        with session_scope() as s:
            symbols = list(s.execute(select(Stock.symbol)).scalars().all())

    from .sync import _refresh_fundamentals

    def worker(sym: str) -> bool:
        fin_ok, _prof_ok = _refresh_fundamentals(sym)
        return fin_ok

    threading.Thread(target=_run_fill, args=("financials", symbols, worker), daemon=True).start()
    return seed_progress("financials")
