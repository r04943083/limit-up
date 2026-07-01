"""财经日历: aggregate forward events (earnings / ex-dividend) across the symbols the user
follows (watchlist + holdings), cache-first per symbol. Company events change slowly, so a
per-day cache keeps the page instant after the first warm.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from ..data import events as ev
from . import market_cache as mc
from .sync import tracked_symbols

_TTL_MIN = 12 * 60


class CalendarEvent(BaseModel):
    date: str
    symbol: str
    type: str            # earnings | ex_dividend
    label: str           # 中文
    detail: str | None = None


class CalendarResult(BaseModel):
    within_days: int
    events: list[CalendarEvent] = []


def get_company_events(symbol: str, *, allow_fetch: bool = True) -> ev.CompanyEvents:
    """Cache-first per-symbol events. allow_fetch=False = pure cache read (no network)."""
    sym = symbol.upper()
    key = f"events:{sym}"
    cached, fetched = mc.read(key)
    if cached and mc.fresh_enough(fetched, is_today=True, today_ttl_min=_TTL_MIN):
        return ev.CompanyEvents.model_validate_json(cached)
    if not allow_fetch:
        if cached:
            return ev.CompanyEvents.model_validate_json(cached)
        return ev.CompanyEvents(symbol=sym)
    try:
        e = ev.fetch_company_events(sym)
        mc.write(key, e.model_dump_json())
        return e
    except Exception:  # noqa: BLE001 - one bad symbol shouldn't sink the calendar
        if cached:
            return ev.CompanyEvents.model_validate_json(cached)
        return ev.CompanyEvents(symbol=sym)


def get_calendar(within_days: int = 30, *, allow_fetch: bool = True,
                 today: dt.date | None = None) -> CalendarResult:
    """Upcoming earnings + ex-dividend events across tracked symbols, soonest first."""
    out: list[CalendarEvent] = []
    for sym in tracked_symbols():
        e = get_company_events(sym, allow_fetch=allow_fetch)
        if ev.is_upcoming(e.earnings_date, within_days=within_days, today=today):
            detail = f"EPS 预期 {e.eps_avg:.2f}" if e.eps_avg is not None else None
            out.append(CalendarEvent(date=e.earnings_date, symbol=sym, type="earnings",
                                     label="财报", detail=detail))
        if ev.is_upcoming(e.ex_dividend_date, within_days=within_days, today=today):
            out.append(CalendarEvent(date=e.ex_dividend_date, symbol=sym, type="ex_dividend",
                                     label="除息"))
    out.sort(key=lambda x: (x.date, x.symbol))
    return CalendarResult(within_days=within_days, events=out)
