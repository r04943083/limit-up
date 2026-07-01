"""Per-company forward events (earnings / ex-dividend / dividend pay dates) via yfinance's
calendar. Feeds the 财经日历 page. Dates come straight from the data source; the LLM never
touches them.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class CompanyEvents(BaseModel):
    symbol: str
    earnings_date: str | None = None       # next scheduled earnings (YYYY-MM-DD)
    ex_dividend_date: str | None = None
    dividend_date: str | None = None       # dividend pay date
    eps_avg: float | None = None            # consensus EPS estimate for the print
    revenue_avg: float | None = None


def _to_date_str(v) -> str | None:  # noqa: ANN001
    if v is None:
        return None
    if isinstance(v, list):
        v = v[0] if v else None
        if v is None:
            return None
    if isinstance(v, str):
        return v[:10]
    iso = getattr(v, "isoformat", None)
    return iso()[:10] if iso else str(v)[:10]


def _num(v) -> float | None:  # noqa: ANN001
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def fetch_company_events(symbol: str) -> CompanyEvents:
    import yfinance as yf

    cal = yf.Ticker(symbol.upper()).calendar or {}
    if not isinstance(cal, dict):
        return CompanyEvents(symbol=symbol.upper())
    return CompanyEvents(
        symbol=symbol.upper(),
        earnings_date=_to_date_str(cal.get("Earnings Date")),
        ex_dividend_date=_to_date_str(cal.get("Ex-Dividend Date")),
        dividend_date=_to_date_str(cal.get("Dividend Date")),
        eps_avg=_num(cal.get("Earnings Average")),
        revenue_avg=_num(cal.get("Revenue Average")),
    )


def is_upcoming(date_str: str | None, *, within_days: int, today: dt.date | None = None) -> bool:
    """True if date_str is today..today+within_days (inclusive). today injectable for tests."""
    if not date_str:
        return False
    try:
        d = dt.date.fromisoformat(date_str[:10])
    except ValueError:
        return False
    t = today or dt.date.today()
    return t <= d <= t + dt.timedelta(days=within_days)
