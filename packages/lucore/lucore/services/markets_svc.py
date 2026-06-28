"""Market-level data: index ticker bar for the bottom status strip.

Cached for a short TTL so the status bar is cheap to poll.
"""
from __future__ import annotations

import time

from pydantic import BaseModel

from ..data.router import get_router
from ..db import session_scope
from ..db.models import Snapshot

# (yfinance symbol, display name, market). Order = display order in the status bar.
INDICES: list[tuple[str, str, str]] = [
    ("^DJI", "道琼斯", "US"),
    ("^IXIC", "纳斯达克", "US"),
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


def get_overview() -> list[OverviewRow]:
    """All synced symbols (from snapshots) with the fields needed for the 机会 page:
    distribution histogram, hot lists, and the sector heatmap."""
    # Imported lazily to avoid a circular import at module load.
    from .research import ResearchBundle

    out: list[OverviewRow] = []
    with session_scope() as s:
        snaps = s.query(Snapshot).all()
        for snap in snaps:
            if not snap.bundle_json:
                continue
            try:
                b = ResearchBundle.model_validate_json(snap.bundle_json)
            except Exception:  # noqa: BLE001
                continue
            out.append(
                OverviewRow(
                    symbol=b.symbol,
                    name=b.quote.name or b.fundamentals.name,
                    market=b.market,
                    sector=b.fundamentals.sector,
                    price=b.quote.price,
                    change_pct=b.quote.change_pct,
                    market_cap=b.fundamentals.market_cap,
                )
            )
    return out
