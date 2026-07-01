"""Market-level data: index ticker bar for the bottom status strip.

Cached for a short TTL so the status bar is cheap to poll.
"""
from __future__ import annotations

import threading
import time

from pydantic import BaseModel

from ..data.router import get_router
from ..db import session_scope
from ..db.models import Snapshot

# (yfinance symbol, display name, market). Order = display order in the status bar.
INDICES: list[tuple[str, str, str]] = [
    ("^DJI", "道琼斯", "US"),
    ("^IXIC", "纳斯达克", "US"),  # 纳斯达克综合指数(全部上市股,~3000+ 只)
    ("^NDX", "纳指100", "US"),   # 纳斯达克100(最大 100 只非金融股);富途「纳指100」对应此处
    ("^GSPC", "标普500", "US"),
    ("^HSI", "恒生指数", "HK"),
    ("000001.SS", "上证指数", "CN"),
]


class IndexQuote(BaseModel):
    symbol: str
    name: str
    market: str
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None


_cache: tuple[float, list[IndexQuote]] | None = None
_TTL = 60.0  # seconds


def get_indices(force: bool = False) -> list[IndexQuote]:
    global _cache
    now = time.time()
    if not force and _cache and now - _cache[0] < _TTL:
        return _cache[1]
    try:
        router = get_router()
    except Exception:  # noqa: BLE001 - cold-init hiccup must not 500 the site-wide status bar
        # Serve the last good cache if any, else placeholder rows (prices fill on next poll).
        return _cache[1] if _cache else [
            IndexQuote(symbol=s, name=n, market=m) for s, n, m in INDICES
        ]
    out: list[IndexQuote] = []
    for sym, name, market in INDICES:
        row = IndexQuote(symbol=sym, name=name, market=market)
        try:
            q = router.get_quote(sym)
            row.price = q.price
            row.change = q.change
            row.change_pct = q.change_pct
        except Exception:  # noqa: BLE001 - a missing index shouldn't break the bar
            pass
        out.append(row)
    _cache = (now, out)
    return out


class OverviewRow(BaseModel):
    symbol: str
    name: str | None = None
    market: str | None = None
    sector: str | None = None
    price: float | None = None
    change_pct: float | None = None
    market_cap: float | None = None


_ov_cache: tuple[float, list[OverviewRow]] | None = None
_OV_TTL = 20.0  # seconds — overview only changes when snapshots re-sync (daily-ish)
_ov_lock = threading.Lock()  # serialize cache read/write + the one-time backfill write


def invalidate_overview() -> None:
    """Drop the overview TTL cache so the next read reflects a just-finished sync."""
    global _ov_cache
    with _ov_lock:
        _ov_cache = None


def _backfill_overview_columns() -> None:
    """One-time: snapshots written before the denormalized columns existed have
    ``market IS NULL``. Parse just those (not every row) and fill the columns, so
    ``get_overview`` never parses JSON again after the first pass."""
    from .research import ResearchBundle

    with session_scope() as s:
        stale = (
            s.query(Snapshot)
            .filter(Snapshot.market.is_(None), Snapshot.bundle_json != "")
            .all()
        )
        for snap in stale:
            try:
                b = ResearchBundle.model_validate_json(snap.bundle_json)
            except Exception:  # noqa: BLE001
                continue
            snap.name = b.quote.name or b.fundamentals.name
            snap.market = b.market
            snap.sector = b.fundamentals.sector
            snap.price = b.quote.price
            snap.change_pct = b.quote.change_pct
            snap.market_cap = b.fundamentals.market_cap


def get_overview(force: bool = False) -> list[OverviewRow]:
    """All synced symbols with the fields the 机会 page needs (distribution histogram,
    hot lists, sector heatmap). Reads denormalized columns only — no per-row JSON parse —
    and caches the result for a short TTL. Serialized by a lock so concurrent callers don't
    double-run the one-time backfill (a write) or race the cache."""
    global _ov_cache
    with _ov_lock:
        now = time.time()
        if not force and _ov_cache and now - _ov_cache[0] < _OV_TTL:
            return _ov_cache[1]

        _backfill_overview_columns()
        with session_scope() as s:
            # Exclude rows never denormalized (blank/unparseable bundle → market stays NULL);
            # emitting them would push all-None entries into the histogram / sector heatmap.
            rows = (
                s.query(
                    Snapshot.symbol,
                    Snapshot.name,
                    Snapshot.market,
                    Snapshot.sector,
                    Snapshot.price,
                    Snapshot.change_pct,
                    Snapshot.market_cap,
                )
                .filter(Snapshot.market.isnot(None))
                .all()
            )
        out = [
            OverviewRow(
                symbol=r[0],
                name=r[1],
                market=r[2],
                sector=r[3],
                price=r[4],
                change_pct=r[5],
                market_cap=r[6],
            )
            for r in rows
        ]
        _ov_cache = (now, out)
        return out
