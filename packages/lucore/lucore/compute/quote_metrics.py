"""Derived per-quote metrics for the Futu-style watchlist columns (pure math, no I/O).

All ratios are returned as FRACTIONS (0.0123 == 1.23%); the UI multiplies by 100.
Inputs come from the cached daily bars + fundamentals — never live-fetched here.
"""
from __future__ import annotations


def shares_outstanding(market_cap: float | None, price: float | None) -> float | None:
    """Approximate float/shares from market cap ÷ price (the only free proxy we have)."""
    if not market_cap or not price or price <= 0:
        return None
    return market_cap / price


def turnover_rate(volume: float | None, shares: float | None) -> float | None:
    """换手率 ≈ 今日成交量 ÷ 总股本 (fraction)."""
    if not volume or not shares or shares <= 0:
        return None
    return volume / shares


def volume_ratio(today_volume: float | None, prior_volumes: list[float]) -> float | None:
    """量比 ≈ 今日成交量 ÷ 之前 N 日平均成交量 (raw ratio, e.g. 2.25)."""
    vols = [v for v in prior_volumes if v and v > 0]
    if not today_volume or not vols:
        return None
    avg = sum(vols) / len(vols)
    return today_volume / avg if avg > 0 else None


def amplitude(high: float | None, low: float | None, prev_close: float | None) -> float | None:
    """振幅 = (最高 - 最低) ÷ 昨收 (fraction)."""
    if high is None or low is None or not prev_close or prev_close <= 0:
        return None
    return (high - low) / prev_close


def pct_from_high(price: float | None, week52_high: float | None) -> float | None:
    """距 52 周高 = 现价 ÷ 52周最高 - 1 (fraction, ≤ 0)."""
    if not price or not week52_high or week52_high <= 0:
        return None
    return price / week52_high - 1
