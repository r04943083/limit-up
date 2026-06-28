"""Deterministic portfolio analytics. Pure functions (no DB/network) for testability;
the service layer resolves prices / FX / sectors and feeds them in.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel


class PositionInput(BaseModel):
    symbol: str
    market: str
    quantity: float
    avg_cost: float | None = None
    price: float | None = None
    currency: str = "USD"
    sector: str | None = None
    name: str | None = None


class Position(BaseModel):
    symbol: str
    name: str | None
    market: str
    sector: str | None
    quantity: float
    avg_cost: float | None
    price: float | None
    currency: str
    market_value: float  # in base currency
    cost_basis: float  # in base currency
    pnl: float
    pnl_pct: float | None
    weight: float  # fraction 0..1


class PortfolioAnalytics(BaseModel):
    base_currency: str
    positions: list[Position]
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float | None
    sector_alloc: dict[str, float]
    market_alloc: dict[str, float]
    top_weight: float
    hhi: float  # Herfindahl concentration index (0..1)
    correlation_symbols: list[str] = []
    correlation_matrix: list[list[float | None]] = []


def compute_portfolio(
    positions: list[PositionInput],
    fx_to_base: dict[str, float],
    base_currency: str = "USD",
) -> PortfolioAnalytics:
    """fx_to_base maps a currency code -> multiplier to convert into base_currency."""
    rows: list[Position] = []
    total_value = 0.0
    total_cost = 0.0
    for p in positions:
        fx = fx_to_base.get(p.currency, 1.0)
        price = p.price or 0.0
        mv = p.quantity * price * fx
        cost = p.quantity * (p.avg_cost or 0.0) * fx
        pnl = mv - cost
        pnl_pct = (pnl / cost * 100) if cost else None
        total_value += mv
        total_cost += cost
        rows.append(
            Position(
                symbol=p.symbol, name=p.name, market=p.market, sector=p.sector,
                quantity=p.quantity, avg_cost=p.avg_cost, price=p.price, currency=p.currency,
                market_value=mv, cost_basis=cost, pnl=pnl, pnl_pct=pnl_pct, weight=0.0,
            )
        )

    sector_alloc: dict[str, float] = {}
    market_alloc: dict[str, float] = {}
    hhi = 0.0
    top_weight = 0.0
    for r in rows:
        w = (r.market_value / total_value) if total_value else 0.0
        r.weight = w
        hhi += w * w
        top_weight = max(top_weight, w)
        sector_alloc[r.sector or "Unknown"] = sector_alloc.get(r.sector or "Unknown", 0.0) + w
        market_alloc[r.market] = market_alloc.get(r.market, 0.0) + w

    total_pnl = total_value - total_cost
    return PortfolioAnalytics(
        base_currency=base_currency,
        positions=rows,
        total_value=total_value,
        total_cost=total_cost,
        total_pnl=total_pnl,
        total_pnl_pct=(total_pnl / total_cost * 100) if total_cost else None,
        sector_alloc=dict(sorted(sector_alloc.items(), key=lambda kv: -kv[1])),
        market_alloc=dict(sorted(market_alloc.items(), key=lambda kv: -kv[1])),
        top_weight=top_weight,
        hhi=hhi,
    )


def compute_correlation(
    returns_by_symbol: dict[str, list[float]],
) -> tuple[list[str], list[list[float | None]]]:
    """Pairwise correlation of daily returns. Symbols with <2 points are dropped."""
    series = {k: pd.Series(v) for k, v in returns_by_symbol.items() if len(v) >= 2}
    symbols = list(series.keys())
    if len(symbols) < 2:
        return symbols, [[1.0] for _ in symbols] if symbols else []
    df = pd.DataFrame(series)
    corr = df.corr()
    matrix: list[list[float | None]] = []
    for a in symbols:
        row: list[float | None] = []
        for b in symbols:
            v = corr.loc[a, b]
            row.append(None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v))
        matrix.append(row)
    return symbols, matrix


def returns_from_closes(closes: list[float]) -> list[float]:
    arr = np.array(closes, dtype=float)
    if len(arr) < 2:
        return []
    return list(np.diff(arr) / arr[:-1])
