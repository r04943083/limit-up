"""Portfolio optimizer service: build an aligned returns matrix from cached daily closes,
run the numpy optimizer, and translate target weights into a whole-share buy plan.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
from pydantic import BaseModel

from ..compute.optimize import (
    AllocationPlan, OptWeights, black_litterman, discrete_allocation, optimize,
)
from ..data.router import get_router
from .portfolio import list_holdings


class OptimizeResult(BaseModel):
    ok: bool = True
    error: str | None = None
    method: str = "max_sharpe"
    weights: OptWeights = OptWeights(method="max_sharpe")
    current_weights: dict[str, float] = {}   # symbol -> current value weight (0..1)
    plan: AllocationPlan | None = None


def _aligned_returns(symbols: list[str], period: str = "1y") -> tuple[list[str], np.ndarray, dict[str, float]]:
    """Return (kept_symbols, (T,N) daily-returns matrix, latest_price_by_symbol) aligned on the
    intersection of trading dates across symbols. Symbols with no cached bars are dropped."""
    router = get_router()
    closes: dict[str, dict[dt.date, float]] = {}
    latest: dict[str, float] = {}
    for s in symbols:
        bars = router.get_ohlcv(s, period=period, refresh=False)
        m = {b.date: b.close for b in bars if b.close is not None}
        if len(m) >= 3:
            closes[s] = m
            latest[s] = m[max(m)]  # latest NON-None close (bars[-1].close could be None)
    kept = [s for s in symbols if s in closes]
    if len(kept) < 1:
        return [], np.zeros((0, 0)), {}
    common = sorted(set.intersection(*[set(closes[s].keys()) for s in kept]))
    if len(common) < 3:
        return kept, np.zeros((0, len(kept))), latest
    mat = np.array([[closes[s][d] for s in kept] for d in common])  # (T, N) prices
    rets = mat[1:] / mat[:-1] - 1.0
    return kept, rets, latest


def optimize_portfolio(portfolio_id: int, method: str = "max_sharpe",
                       capital: float | None = None) -> OptimizeResult:
    holdings = [(h.symbol, h.quantity) for h in list_holdings(portfolio_id) if h.quantity]
    if len(holdings) < 2:
        return OptimizeResult(ok=False, error="need at least 2 holdings", method=method)

    symbols = [s for s, _ in holdings]
    kept, rets, latest = _aligned_returns(symbols)
    if rets.shape[0] < 2 or len(kept) < 2:
        return OptimizeResult(ok=False, error="insufficient aligned price history", method=method)

    if method == "black_litterman":
        from .research import load_snapshot
        # Market prior = current value weights.
        cur_vals = {s: q * latest.get(s, 0.0) for s, q in holdings if s in kept}
        tot = sum(cur_vals.values()) or 1.0
        mkt = [cur_vals.get(s, 0.0) / tot for s in kept]
        # Deterministic views: each symbol's analyst-target upside is an absolute-return view, so
        # BL tilts the equilibrium toward analyst-favored names (no LLM — pure data-derived).
        views: dict[str, float] = {}
        for s in kept:
            snap = load_snapshot(s)
            if snap and snap.fundamentals.target_mean and snap.quote.price:
                views[s] = round((snap.fundamentals.target_mean / snap.quote.price - 1) * 100, 2)
        w = black_litterman(kept, rets, mkt, views=views)
    else:
        w = optimize(kept, rets, method=method)

    # Current value weights for a before/after comparison.
    cur_vals = {s: q * latest.get(s, 0.0) for s, q in holdings if s in kept}
    tot_val = sum(cur_vals.values())
    current = {s: round(cur_vals[s] / tot_val, 4) for s in kept} if tot_val > 0 else {}

    cap = capital if (capital and capital > 0) else (tot_val or 100_000.0)
    prices = [latest.get(s, 0.0) for s in kept]
    plan = discrete_allocation(kept, w.weights, prices, cap)

    return OptimizeResult(ok=True, method=w.method, weights=w, current_weights=current, plan=plan)
