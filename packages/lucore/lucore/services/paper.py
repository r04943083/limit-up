"""Paper trading (#8).

A virtual cash account. Trades fill at the cache-quote price (cache-first, no live
fetch on the hot path). Positions and P&L are *derived* from the trade ledger +
current cache prices — never stored, so they always reflect the latest snapshot.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import select

from ..db import session_scope
from ..db.models import PaperAccount, PaperTrade, Snapshot
from .research import ResearchBundle, get_research

DEFAULT_NAME = "模拟账户"
START_CASH = 100_000.0


class TradeOut(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: float
    price: float
    note: str | None
    created_at: dt.datetime


class PaperPosition(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    price: float | None
    market_value: float
    cost_basis: float
    pnl: float
    pnl_pct: float | None
    weight: float


class PaperAccountOut(BaseModel):
    id: int
    name: str
    cash: float
    starting_cash: float
    base_currency: str
    positions: list[PaperPosition]
    invested: float
    equity: float  # cash + invested
    total_pnl: float
    total_return_pct: float | None
    trades: list[TradeOut]


def _cache_price(symbol: str) -> float | None:
    """Last price from the stored snapshot (instant). Falls back to a cached research load."""
    sym = symbol.upper()
    with session_scope() as s:
        snap = s.get(Snapshot, sym)
        if snap and snap.bundle_json:
            try:
                return ResearchBundle.model_validate_json(snap.bundle_json).quote.price
            except Exception:  # noqa: BLE001
                pass
    try:
        return get_research(sym, cached=True).quote.price
    except Exception:  # noqa: BLE001
        return None


def ensure_account() -> int:
    with session_scope() as s:
        row = s.execute(select(PaperAccount).limit(1)).scalar_one_or_none()
        if row is None:
            row = PaperAccount(name=DEFAULT_NAME, cash=START_CASH, starting_cash=START_CASH)
            s.add(row)
            s.flush()
        return row.id


def _positions(trades: list[PaperTrade]) -> dict[str, dict]:
    """Average-cost positions from the trade ledger (oldest first)."""
    pos: dict[str, dict] = {}
    for t in sorted(trades, key=lambda x: (x.created_at or dt.datetime.min, x.id)):
        p = pos.setdefault(t.symbol, {"qty": 0.0, "cost": 0.0})
        if t.side == "buy":
            p["cost"] += t.quantity * t.price
            p["qty"] += t.quantity
        else:  # sell — realize at average cost, reduce basis proportionally
            if p["qty"] > 0:
                avg = p["cost"] / p["qty"]
                sold = min(t.quantity, p["qty"])
                p["cost"] -= avg * sold
                p["qty"] -= sold
    return {sym: p for sym, p in pos.items() if p["qty"] > 1e-9}


def get_account() -> PaperAccountOut:
    acct_id = ensure_account()
    with session_scope() as s:
        acct = s.get(PaperAccount, acct_id)
        trades = list(
            s.execute(
                select(PaperTrade).where(PaperTrade.account_id == acct_id)
                .order_by(PaperTrade.created_at.desc())
            ).scalars()
        )
        cash, starting, name, ccy = acct.cash, acct.starting_cash, acct.name, acct.base_currency

    held = _positions(trades)
    positions: list[PaperPosition] = []
    invested = 0.0
    for sym, p in held.items():
        avg = p["cost"] / p["qty"] if p["qty"] else 0.0
        price = _cache_price(sym)
        mv = (price or avg) * p["qty"]
        invested += mv
        pnl = mv - p["cost"]
        positions.append(PaperPosition(
            symbol=sym, quantity=round(p["qty"], 4), avg_cost=round(avg, 4), price=price,
            market_value=round(mv, 2), cost_basis=round(p["cost"], 2), pnl=round(pnl, 2),
            pnl_pct=(pnl / p["cost"] if p["cost"] else None), weight=0.0,
        ))
    equity = cash + invested
    for pos in positions:
        pos.weight = pos.market_value / equity if equity else 0.0
    positions.sort(key=lambda x: x.market_value, reverse=True)
    total_pnl = equity - starting
    return PaperAccountOut(
        id=acct_id, name=name, cash=round(cash, 2), starting_cash=starting, base_currency=ccy,
        positions=positions, invested=round(invested, 2), equity=round(equity, 2),
        total_pnl=round(total_pnl, 2),
        total_return_pct=(total_pnl / starting if starting else None),
        trades=[TradeOut(
            id=t.id, symbol=t.symbol, side=t.side, quantity=t.quantity, price=t.price,
            note=t.note, created_at=t.created_at,
        ) for t in trades],
    )


class TradeError(ValueError):
    pass


def trade(symbol: str, side: str, quantity: float, *, note: str | None = None) -> PaperAccountOut:
    sym = symbol.strip().upper()
    side = side.lower()
    if side not in ("buy", "sell"):
        raise TradeError("side must be buy or sell")
    if quantity <= 0:
        raise TradeError("quantity must be positive")
    price = _cache_price(sym)
    if price is None or price <= 0:
        raise TradeError(f"no cache price for {sym} — sync it first")
    acct_id = ensure_account()
    with session_scope() as s:
        acct = s.get(PaperAccount, acct_id)
        if side == "buy":
            cost = price * quantity
            if cost > acct.cash + 1e-6:
                raise TradeError(f"现金不足:需 {cost:.2f},余 {acct.cash:.2f}")
            acct.cash -= cost
        else:
            existing = list(s.execute(
                select(PaperTrade).where(PaperTrade.account_id == acct_id, PaperTrade.symbol == sym)
            ).scalars())
            held = _positions(existing).get(sym, {"qty": 0.0})
            if quantity > held["qty"] + 1e-6:
                raise TradeError(f"持仓不足:持有 {held['qty']:.4f} 股")
            acct.cash += price * quantity
        s.add(PaperTrade(
            account_id=acct_id, symbol=sym, side=side, quantity=quantity, price=price, note=note,
        ))
    return get_account()


def reset() -> PaperAccountOut:
    acct_id = ensure_account()
    with session_scope() as s:
        for t in s.execute(select(PaperTrade).where(PaperTrade.account_id == acct_id)).scalars():
            s.delete(t)
        acct = s.get(PaperAccount, acct_id)
        acct.cash = acct.starting_cash
    return get_account()
