"""Financials service: cache-first statements + a DCF view for the deep-research page.

Statements change quarterly, so they're cached in ``financials_cache`` and refreshed
lazily (≥7 days stale). The DCF itself is cheap deterministic math (compute/valuation),
recomputed per request so the UI can drive the assumptions live.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from ..compute.valuation import DcfResult, dcf, implied_growth_from_fcf
from ..data.base import Financials
from ..data.router import get_router
from ..db import session_scope
from ..db.models import FinancialsCache

_STALE_DAYS = 7


def get_financials_cached(symbol: str, refresh: bool = True) -> Financials:
    sym = symbol.strip().upper()
    with session_scope() as s:
        row = s.get(FinancialsCache, sym)
        fresh = False
        if row is not None and row.fetched_at is not None:
            age = dt.datetime.now(dt.timezone.utc) - _aware(row.fetched_at)
            fresh = age.days < _STALE_DAYS
        if row is not None and (fresh or not refresh):
            try:
                return Financials.model_validate_json(row.payload_json)
            except Exception:  # noqa: BLE001 - corrupt cache -> refetch below
                pass

    fin = get_router().get_financials(sym)
    payload = fin.model_dump_json()
    with session_scope() as s:
        row = s.get(FinancialsCache, sym)
        if row is None:
            s.add(FinancialsCache(symbol=sym, payload_json=payload,
                                  fetched_at=dt.datetime.now(dt.timezone.utc)))
        else:
            row.payload_json = payload
            row.fetched_at = dt.datetime.now(dt.timezone.utc)
    return fin


def _aware(d: dt.datetime) -> dt.datetime:
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


class DcfView(BaseModel):
    """DCF result enriched with the current price + upside for the UI."""
    symbol: str
    currency: str | None = None
    price: float | None = None
    upside_pct: float | None = None
    has_fcf: bool = True
    result: DcfResult | None = None


def compute_dcf(
    symbol: str,
    growth: float | None = None,
    discount: float | None = None,
    terminal_growth: float | None = None,
    years: int | None = None,
) -> DcfView:
    sym = symbol.strip().upper()
    fin = get_financials_cached(sym)

    # Base FCF = latest annual free cash flow (newest first).
    fcf_base = next((v for v in fin.fcf if v is not None), None)
    price = None
    try:
        price = get_router().get_quote(sym).price
    except Exception:  # noqa: BLE001
        price = None

    if fcf_base is None or fcf_base <= 0 or not fin.shares:
        return DcfView(symbol=sym, currency=fin.currency, price=price, has_fcf=False)

    g = growth if growth is not None else (implied_growth_from_fcf(fin.fcf) or 0.08)
    res = dcf(
        fcf_base=fcf_base,
        growth=g,
        discount=discount if discount is not None else 0.09,
        terminal_growth=terminal_growth if terminal_growth is not None else 0.025,
        years=years if years is not None else 5,
        shares=fin.shares,
        net_debt=fin.net_debt or 0.0,
    )
    upside = None
    if res.intrinsic_per_share is not None and price:
        upside = (res.intrinsic_per_share - price) / price * 100.0
    return DcfView(
        symbol=sym, currency=fin.currency, price=price, upside_pct=upside,
        has_fcf=True, result=res,
    )
