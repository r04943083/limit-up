"""Portfolio optimization (mean-variance, risk-parity, Black-Litterman) + integer share
allocation. Pure numpy — no cvxpy/scipy — so it stays a dependency-light, deterministic
compute layer the LLM only narrates.

Long-only is enforced by projecting the closed-form solutions onto the simplex (clip
negatives, renormalize); for the small books this app deals with that is a faithful,
transparent approximation of a long-only optimizer.
"""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel

_TRADING_DAYS = 252


class OptWeights(BaseModel):
    method: str
    symbols: list[str] = []
    weights: list[float] = []            # aligned to symbols, sums to 1
    expected_return_pct: float | None = None   # annualized
    volatility_pct: float | None = None        # annualized
    sharpe: float | None = None
    note: str | None = None              # e.g. a solver-degeneration fallback disclosure


class Allocation(BaseModel):
    symbol: str
    weight_pct: float
    shares: int
    value: float


class AllocationPlan(BaseModel):
    capital: float
    allocations: list[Allocation] = []
    leftover_cash: float = 0.0


def _project_simplex(w: np.ndarray) -> np.ndarray:
    """Long-only projection: clip negatives, renormalize to sum 1 (equal-weight if degenerate)."""
    w = np.clip(w, 0.0, None)
    s = w.sum()
    if s <= 1e-12:
        return np.full(len(w), 1.0 / len(w))
    return w / s


def shrink_cov(returns: np.ndarray, shrink: float = 0.1) -> np.ndarray:
    """Sample covariance shrunk toward its diagonal (a light Ledoit-Wolf-style regularizer that
    keeps the matrix invertible / well-conditioned). ``returns`` is (T, N) daily returns."""
    cov = np.cov(returns, rowvar=False)
    cov = np.atleast_2d(cov)
    diag = np.diag(np.diag(cov))
    return (1 - shrink) * cov + shrink * diag


def _annualize(mu_daily: np.ndarray, cov_daily: np.ndarray, w: np.ndarray) -> tuple[float, float, float]:
    ret = float(mu_daily @ w) * _TRADING_DAYS
    var = float(w @ cov_daily @ w) * _TRADING_DAYS
    vol = float(np.sqrt(max(var, 0.0)))
    sharpe = ret / vol if vol > 1e-9 else 0.0
    return ret * 100, vol * 100, sharpe


def optimize(symbols: list[str], returns: np.ndarray, method: str = "max_sharpe") -> OptWeights:
    """Compute long-only weights from a (T, N) daily-returns matrix.

    method: max_sharpe | min_variance | risk_parity (inverse-volatility).
    """
    n = len(symbols)
    if n == 0 or returns.ndim != 2 or returns.shape[1] != n or returns.shape[0] < 2:
        return OptWeights(method=method, symbols=symbols,
                          weights=[1.0 / n] * n if n else [])

    mu = returns.mean(axis=0)                    # daily mean returns
    cov = shrink_cov(returns)
    cov_inv = np.linalg.pinv(cov)
    note: str | None = None

    if method == "min_variance":
        w = cov_inv @ np.ones(n)
    elif method == "risk_parity":
        vol = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
        w = 1.0 / vol                            # inverse-volatility risk budgeting
    else:  # max_sharpe — tangency portfolio (rf = 0)
        method = "max_sharpe"
        raw = cov_inv @ mu
        if np.clip(raw, 0.0, None).sum() <= 1e-12:
            # Every asset has non-positive expected return this window → the long-only tangency
            # portfolio is empty. Fall back to the sensible defensive portfolio and disclose it.
            w = cov_inv @ np.ones(n)
            note = "本窗口多头无正预期收益,已回退最小方差组合"
        else:
            w = raw

    w = _project_simplex(np.asarray(w, dtype=float))
    ret_pct, vol_pct, sharpe = _annualize(mu, cov, w)
    return OptWeights(
        method=method, symbols=symbols, weights=[round(float(x), 4) for x in w],
        expected_return_pct=round(ret_pct, 2), volatility_pct=round(vol_pct, 2),
        sharpe=round(sharpe, 2), note=note,
    )


def black_litterman(
    symbols: list[str], returns: np.ndarray, market_weights: list[float],
    views: dict[str, float], *, tau: float = 0.05, view_conf: float = 0.5,
) -> OptWeights:
    """Black-Litterman posterior weights blending the market-implied prior with per-asset
    absolute return ``views`` (annualized expected-return %, keyed by symbol). ``market_weights``
    is the current book (e.g. cap/holdings weights). Returns long-only projected weights.
    """
    n = len(symbols)
    if n == 0 or returns.shape[0] < 2:
        return OptWeights(method="black_litterman", symbols=symbols,
                          weights=[1.0 / n] * n if n else [])

    cov = shrink_cov(returns) * _TRADING_DAYS     # annualized covariance
    w_mkt = _project_simplex(np.asarray(market_weights, dtype=float))
    # Reverse-optimize the implied equilibrium returns: Π = δ Σ w_mkt (risk aversion δ≈2.5).
    delta = 2.5
    pi = delta * cov @ w_mkt

    # Build the views: one absolute view per symbol that has one (P = identity rows).
    idx = [i for i, s in enumerate(symbols) if s in views]
    if not idx:
        post = pi
    else:
        P = np.zeros((len(idx), n))
        q = np.zeros(len(idx))
        for r, i in enumerate(idx):
            P[r, i] = 1.0
            q[r] = views[symbols[i]] / 100.0      # % → fraction
        # Floor the view-uncertainty diagonal so a zero-variance (flat-price) asset doesn't get
        # omega=0 → pinv(0)=0, which would silently DISCARD the view instead of enforcing it.
        omega = np.diag(np.clip(np.diag(P @ (tau * cov) @ P.T), 1e-10, None)) / max(view_conf, 1e-6)
        tau_cov = tau * cov
        A = np.linalg.pinv(tau_cov) + P.T @ np.linalg.pinv(omega) @ P
        b = np.linalg.pinv(tau_cov) @ pi + P.T @ np.linalg.pinv(omega) @ q
        post = np.linalg.pinv(A) @ b

    cov_inv = np.linalg.pinv(cov)
    w = _project_simplex(cov_inv @ post)
    mu_daily = returns.mean(axis=0)
    ret_pct, vol_pct, sharpe = _annualize(mu_daily, shrink_cov(returns), w)
    return OptWeights(
        method="black_litterman", symbols=symbols, weights=[round(float(x), 4) for x in w],
        expected_return_pct=round(ret_pct, 2), volatility_pct=round(vol_pct, 2), sharpe=round(sharpe, 2),
    )


def discrete_allocation(symbols: list[str], weights: list[float], prices: list[float],
                        capital: float) -> AllocationPlan:
    """Convert target weights into whole-share buys within ``capital`` (greedy: floor each,
    then spend leftover on the cheapest affordable names)."""
    allocs: list[Allocation] = []
    cash = capital
    for sym, w, px in zip(symbols, weights, prices):
        if px and px > 0 and w > 0:
            shares = int((w * capital) // px)
            cost = shares * px
            cash -= cost
            allocs.append(Allocation(symbol=sym, weight_pct=round(w * 100, 2), shares=shares, value=round(cost, 2)))
        else:
            allocs.append(Allocation(symbol=sym, weight_pct=round(w * 100, 2), shares=0, value=0.0))

    # Greedy top-up: repeatedly buy one more share of the cheapest name we can still afford.
    priced = [(i, prices[i]) for i in range(len(symbols)) if prices[i] and prices[i] > 0 and weights[i] > 0]
    priced.sort(key=lambda t: t[1])
    changed = True
    while changed and priced:
        changed = False
        for i, px in priced:
            if px <= cash:
                allocs[i].shares += 1
                allocs[i].value = round(allocs[i].value + px, 2)
                cash -= px
                changed = True
                break
    return AllocationPlan(capital=round(capital, 2), allocations=allocs, leftover_cash=round(cash, 2))
