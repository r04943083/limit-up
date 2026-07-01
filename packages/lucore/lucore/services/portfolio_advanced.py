"""Advanced portfolio analytics services: Brinson attribution (vs an equal-weight benchmark of
the same holdings) and tax-loss-harvesting scan. Cache-first (no live network on the hot path).
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import select

from ..compute.attribution import Attribution, brinson
from ..compute.taxlots import TlhResult, tlh_scan
from ..data.router import get_router
from ..db import session_scope
from ..db.models import Holding
from .portfolio import list_holdings
from .research import get_research, load_snapshot


def _period_return(symbol: str, period: str = "1y") -> float | None:
    bars = get_router().get_ohlcv(symbol, period=period, refresh=False)
    closes = [b.close for b in bars if b.close is not None]
    if len(closes) < 2 or closes[0] <= 0:
        return None
    return closes[-1] / closes[0] - 1.0


class AttributionResult(BaseModel):
    ok: bool = True
    error: str | None = None
    attribution: Attribution = Attribution()


def compute_attribution(portfolio_id: int) -> AttributionResult:
    """Brinson attribution by sector: value-weighted portfolio vs an equal-weight benchmark of
    the same holdings. Isolates whether the user's sizing (allocation) and stock picks
    (selection) beat naively holding everything equally."""
    holdings = [(h.symbol, h.quantity) for h in list_holdings(portfolio_id) if h.quantity]
    if len(holdings) < 2:
        return AttributionResult(ok=False, error="need at least 2 holdings")

    # Gather per-holding: sector, value, period return.
    rows = []
    for sym, qty in holdings:
        try:
            rb = get_research(sym, cached=True)
            sector = rb.fundamentals.sector or "其他"
            price = rb.quote.price
        except Exception:  # noqa: BLE001
            sector, price = "其他", None
        ret = _period_return(sym)
        if price is None or ret is None:
            continue
        rows.append({"symbol": sym, "sector": sector, "value": qty * price, "ret": ret})

    if len(rows) < 2:
        return AttributionResult(ok=False, error="insufficient price history")

    total_value = sum(r["value"] for r in rows) or 1.0
    n = len(rows)
    sectors: dict[str, list] = {}
    for r in rows:
        sectors.setdefault(r["sector"], []).append(r)

    segs = []
    for sector, items in sectors.items():
        val = sum(i["value"] for i in items)
        wp = val / total_value
        rp = sum(i["value"] * i["ret"] for i in items) / val if val > 0 else 0.0  # value-weighted
        wb = len(items) / n                                                        # equal-weight
        rb = sum(i["ret"] for i in items) / len(items)                             # equal-weight
        segs.append({"segment": sector, "wp": wp, "rp": rp, "wb": wb, "rb": rb})

    return AttributionResult(attribution=brinson(segs, benchmark="等权基准"))


class TlhServiceResult(BaseModel):
    ok: bool = True
    error: str | None = None
    result: TlhResult = TlhResult()


def compute_tlh(portfolio_id: int, today: dt.date | None = None) -> TlhServiceResult:
    """Scan holdings for tax-loss-harvesting candidates (unrealized loss), flagging wash-sale
    risk for lots added within the last 30 days."""
    t = today or dt.date.today()
    with session_scope() as s:
        rows = s.execute(
            select(Holding).where(Holding.portfolio_id == portfolio_id)
        ).scalars().all()
        raw = [(h.symbol, h.quantity, h.avg_cost, h.created_at) for h in rows]

    positions = []
    for sym, qty, avg_cost, created_at in raw:
        if not qty or avg_cost is None:
            continue
        snap = load_snapshot(sym)
        price = snap.quote.price if snap else None
        if price is None:
            continue
        days_held = None
        if created_at is not None:
            cd = created_at.date() if hasattr(created_at, "date") else created_at
            days_held = (t - cd).days
        positions.append({"symbol": sym, "quantity": qty, "avg_cost": avg_cost,
                          "price": price, "days_held": days_held})

    return TlhServiceResult(result=tlh_scan(positions))
