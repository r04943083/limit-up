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
    # Extra detail filled by the deep "一键更新" (sync_all). Optional so single-symbol
    # /sync responses stay valid without them.
    financials_synced: int = 0
    profiles_synced: int = 0
    skipped_fresh: int = 0  # symbols skipped because their snapshot was still fresh
    feeds: dict[str, bool] = {}  # global market feeds refreshed: indices / limit_up / ...


def tracked_symbols() -> list[str]:
    """Every symbol the user follows: watchlist items + portfolio holdings, deduped."""
    with session_scope() as s:
        wl = s.execute(select(WatchlistItem.symbol)).scalars().all()
        hold = s.execute(select(Holding.symbol)).scalars().all()
    seen: dict[str, None] = {}
    for sym in [*wl, *hold]:
        seen.setdefault(sym.upper(), None)
    return list(seen)


def _fresh_symbols(symbols: list[str], max_age_hours: float) -> set[str]:
    """Of `symbols`, those whose snapshot was synced within `max_age_hours` — safe to skip
    on a re-sync. Makes repeated 「全部更新」 near-instant instead of re-fetching everything."""
    if max_age_hours <= 0:
        return set()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=max_age_hours)
    want = {s.upper() for s in symbols}
    fresh: set[str] = set()
    with session_scope() as s:
        for snap in s.execute(select(Snapshot)).scalars():
            if snap.symbol.upper() in want and snap.synced_at is not None:
                synced = snap.synced_at
                if synced.tzinfo is None:
                    synced = synced.replace(tzinfo=dt.timezone.utc)
                if synced >= cutoff:
                    fresh.add(snap.symbol.upper())
    return fresh


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
# polite to the data source and to limit SQLite write contention (single writer) —
# too many writers just queue on the write lock, so 8 balances throughput vs contention.
_SYNC_WORKERS = 8


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


def _refresh_fundamentals(symbol: str) -> tuple[bool, bool]:
    """Fill the *slow-moving* per-stock caches (financials + profile) for a tracked symbol.

    These are normally lazy-loaded only when the user opens 财报/概况 — which is why most
    stocks show empty there. The deep 一键更新 pre-warms them for the user's own stocks so
    those pages are instant. Cache-first: `get_*_cached` skips symbols that are still fresh,
    so re-runs are cheap. Returns (financials_ok, profile_ok)."""
    from .calendar_svc import get_company_events
    from .financials import get_financials_cached
    from .profile import get_profile_cached

    fin_ok = prof_ok = False
    try:
        get_financials_cached(symbol)
        fin_ok = True
    except Exception:  # noqa: BLE001 - one stock's missing statements shouldn't fail the run
        pass
    try:
        get_profile_cached(symbol)
        prof_ok = True
    except Exception:  # noqa: BLE001
        pass
    try:
        get_company_events(symbol)  # warm the 财经日历 cache so that page is instant
    except Exception:  # noqa: BLE001 - events are best-effort
        pass
    return fin_ok, prof_ok


def _refresh_global_feeds() -> dict[str, bool]:
    """Refresh the market-wide feeds (small in number, high value) — indices + the A-share
    limit-up pool / dragon-tiger / HSGT for today. Each is isolated so one source being down
    doesn't sink the others."""
    feeds: dict[str, bool] = {}

    def _try(name: str, fn) -> None:  # noqa: ANN001
        try:
            fn()
            feeds[name] = True
        except Exception:  # noqa: BLE001
            feeds[name] = False

    from .cn_market import get_dragon_tiger, get_hsgt_summary, get_limit_up_pool
    from .markets_svc import get_indices
    from .us_market import get_movers

    _try("indices", lambda: get_indices(force=True))
    _try("limit_up", lambda: get_limit_up_pool())
    _try("dragon_tiger", lambda: get_dragon_tiger())
    _try("hsgt", lambda: get_hsgt_summary())
    # US discovery movers (the 发现 page): warm the core boards so it loads instantly.
    for _kind in ("day_gainers", "day_losers", "most_actives"):
        _try(f"us_{_kind}", lambda k=_kind: get_movers(k))
    return feeds


def sync_all(deep: bool = True, max_age_hours: float = 6.0) -> SyncResult:
    """One-click refresh of everything that's cheap to keep current:

    1. A research snapshot (quote + fundamentals + technical + news) for every tracked symbol.
    2. (deep) financials + profile for those same symbols — fills the usually-empty 财报/概况.
    3. Global market feeds: indices + A-share limit-up / dragon-tiger / HSGT.

    Staleness-aware: symbols whose snapshot was synced within `max_age_hours` are skipped, so a
    second 「全部更新」 in the same session is near-instant (only the global feeds refresh).
    Pass `max_age_hours=0` to force a full refresh. Per-stock AI + the daily briefing are NOT
    triggered here (LLM cost; own buttons / 08:30 scheduler)."""
    tracked = tracked_symbols()
    fresh = _fresh_symbols(tracked, max_age_hours)
    symbols = [s for s in tracked if s.upper() not in fresh]
    result = sync_symbols(symbols)
    result.skipped_fresh = len(fresh)
    result.requested = len(tracked)  # report against everything tracked, not just the stale subset

    if deep and symbols:
        fin_n = prof_n = 0
        with ThreadPoolExecutor(max_workers=min(_SYNC_WORKERS, len(symbols))) as pool:
            for fin_ok, prof_ok in pool.map(_refresh_fundamentals, symbols):
                fin_n += int(fin_ok)
                prof_n += int(prof_ok)
        result.financials_synced = fin_n
        result.profiles_synced = prof_n

    result.feeds = _refresh_global_feeds()
    # The overview page reads a short-TTL cache; drop it so it reflects this sync at once.
    from .markets_svc import invalidate_overview
    invalidate_overview()
    return result


class FreshnessRow(BaseModel):
    symbol: str
    synced_at: dt.datetime | None


def freshness() -> list[FreshnessRow]:
    """Per-symbol last-synced time, newest first — drives the 'data updated at' UI."""
    with session_scope() as s:
        rows = s.execute(select(Snapshot).order_by(Snapshot.synced_at.desc())).scalars().all()
        return [FreshnessRow(symbol=r.symbol, synced_at=r.synced_at) for r in rows]
