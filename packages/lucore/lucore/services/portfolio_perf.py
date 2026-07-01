"""Portfolio performance tear-sheet.

Reconstructs a dated equity curve from the *current* holdings valued over ~1y of cached
daily closes (a "composition tear-sheet": what this basket would have done), converts each
symbol to the base currency at the current FX rate, and runs the deterministic tear-sheet
against an SPY benchmark. All numbers come from compute + cached data; the LLM never touches
this. Because it holds the composition fixed, it is a risk/return profile of the *current*
basket, not a trade-by-trade P&L history.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from ..compute.tearsheet import Tearsheet, tearsheet
from ..data.fx import fx_map
from ..data.router import get_router
from ..markets import MARKET_CURRENCY, infer_market
from .portfolio import list_holdings


class PortfolioTearsheet(BaseModel):
    ok: bool = True
    error: str | None = None
    base_currency: str = "USD"
    benchmark: str = "SPY"
    start: str | None = None      # first date of the reconstructed curve
    end: str | None = None
    tearsheet: Tearsheet = Tearsheet()


def _dated_closes(symbol: str, period: str = "1y", *, refresh: bool = False) -> dict[dt.date, float]:
    bars = get_router().get_ohlcv(symbol, period=period, refresh=refresh)
    return {b.date: b.close for b in bars if b.close is not None}


def compute_portfolio_tearsheet(portfolio_id: int, base_currency: str = "USD") -> PortfolioTearsheet:
    holdings = [(h.symbol, h.quantity) for h in list_holdings(portfolio_id) if h.quantity]
    if not holdings:
        return PortfolioTearsheet(ok=False, error="empty portfolio", base_currency=base_currency)

    # FX: convert each symbol's native price to base currency at the current rate.
    currencies = {base_currency}
    ccy_by_sym: dict[str, str] = {}
    for sym, _ in holdings:
        c = MARKET_CURRENCY.get(infer_market(sym), "USD")
        ccy_by_sym[sym] = c
        currencies.add(c)
    try:
        fx = fx_map(currencies, base_currency)  # currency -> multiplier to base
    except Exception:  # noqa: BLE001 - a failed FX lookup shouldn't 502 the whole tear-sheet
        fx = {c: 1.0 for c in currencies}  # degrade to unconverted (fine for a USD-only basket)

    closes = {sym: _dated_closes(sym) for sym, _ in holdings}
    closes = {s: c for s, c in closes.items() if c}  # drop symbols with no cached bars
    if not closes:
        return PortfolioTearsheet(ok=False, error="no cached price history", base_currency=base_currency)
    held = [(s, q) for s, q in holdings if s in closes]

    all_dates = sorted(set().union(*[set(c.keys()) for c in closes.values()]))
    last: dict[str, float | None] = {s: None for s, _ in held}
    dates: list[dt.date] = []
    equities: list[float] = []
    for d in all_dates:
        for s, _ in held:
            if d in closes[s]:
                last[s] = closes[s][d]
        if all(last[s] is not None for s, _ in held):  # curve starts once every symbol is priced
            val = sum(q * last[s] * fx.get(ccy_by_sym[s], 1.0) for s, q in held)
            dates.append(d)
            equities.append(val)

    if len(equities) < 2:
        return PortfolioTearsheet(ok=False, error="insufficient price history", base_currency=base_currency)

    # SPY benchmark aligned to the same dates (forward-filled). One live fetch is fine here
    # (tear-sheet is an explicit action, not a page-load hot path).
    bench: list[float] | None = None
    try:
        spy = _dated_closes("SPY", refresh=True)
        if spy:
            b: list[float] = []
            lastb: float | None = None
            ok = True
            for d in dates:
                if d in spy:
                    lastb = spy[d]
                if lastb is None:
                    ok = False
                    break
                b.append(lastb)
            bench = b if ok else None
    except Exception:  # noqa: BLE001 - benchmark is optional
        bench = None

    ts = tearsheet(dates, equities, equities[0], benchmark=bench)
    return PortfolioTearsheet(
        base_currency=base_currency,
        start=dates[0].isoformat(), end=dates[-1].isoformat(),
        tearsheet=ts,
    )
