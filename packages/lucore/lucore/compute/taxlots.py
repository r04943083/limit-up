"""Tax-lot accounting: realized gains under FIFO / LIFO / HIFO cost-basis methods, and
tax-loss-harvesting (TLH) candidate detection with a 30-day wash-sale caveat. Pure math —
deterministic tax figures the LLM only explains.
"""
from __future__ import annotations

from pydantic import BaseModel

WASH_SALE_DAYS = 30


class Lot(BaseModel):
    date: str            # acquisition date (YYYY-MM-DD), for FIFO/LIFO ordering
    quantity: float
    price: float          # cost per share


class RealizedResult(BaseModel):
    method: str
    sold_qty: float
    proceeds: float
    cost_basis: float
    realized_gain: float
    short_note: str | None = None


def _order(lots: list[Lot], method: str) -> list[Lot]:
    if method == "lifo":
        return sorted(lots, key=lambda x: x.date, reverse=True)
    if method == "hifo":
        return sorted(lots, key=lambda x: x.price, reverse=True)  # highest cost first (min gain)
    return sorted(lots, key=lambda x: x.date)  # fifo (default)


def realized_gain(lots: list[Lot], sell_qty: float, sell_price: float,
                  method: str = "fifo") -> RealizedResult:
    """Realized gain from selling ``sell_qty`` at ``sell_price``, consuming lots in the order
    dictated by ``method``. Caps at available quantity."""
    method = method if method in ("fifo", "lifo", "hifo") else "fifo"
    ordered = _order(lots, method)
    remaining = max(0.0, sell_qty)
    cost = 0.0
    consumed = 0.0
    for lot in ordered:
        if remaining <= 1e-9:
            break
        take = min(lot.quantity, remaining)
        cost += take * lot.price
        consumed += take
        remaining -= take
    proceeds = consumed * sell_price
    return RealizedResult(
        method=method, sold_qty=round(consumed, 4), proceeds=round(proceeds, 2),
        cost_basis=round(cost, 2), realized_gain=round(proceeds - cost, 2),
    )


class TlhCandidate(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    price: float
    unrealized_loss: float       # positive number = harvestable loss (base currency)
    loss_pct: float              # negative % (e.g. -12.3)
    wash_sale_risk: bool         # bought within the last 30 days → selling may trigger wash sale
    note: str | None = None


class TlhResult(BaseModel):
    candidates: list[TlhCandidate] = []
    total_harvestable_loss: float = 0.0


def tlh_scan(positions: list[dict]) -> TlhResult:
    """Find tax-loss-harvesting candidates among positions.

    Each position: {symbol, quantity, avg_cost, price, days_held}. A candidate is any position
    at an unrealized loss (price < avg_cost). ``days_held < 30`` flags wash-sale risk (a recent
    purchase — harvesting then repurchasing within 30 days would disallow the loss).
    """
    cands: list[TlhCandidate] = []
    total = 0.0
    for p in positions:
        qty = float(p.get("quantity", 0) or 0)
        avg = p.get("avg_cost")
        price = p.get("price")
        if not qty or avg is None or price is None or price >= avg:
            continue
        loss = (avg - price) * qty
        days_held = p.get("days_held")
        wash = days_held is not None and days_held < WASH_SALE_DAYS
        total += loss
        cands.append(TlhCandidate(
            symbol=str(p.get("symbol", "")),
            quantity=round(qty, 4), avg_cost=round(float(avg), 4), price=round(float(price), 4),
            unrealized_loss=round(loss, 2), loss_pct=round((price / avg - 1) * 100, 2),
            wash_sale_risk=wash,
            note="近 30 天买入,注意洗售规则" if wash else None,
        ))
    cands.sort(key=lambda c: -c.unrealized_loss)
    return TlhResult(candidates=cands, total_harvestable_loss=round(total, 2))
