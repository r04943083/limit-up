"""Equity-curve performance metrics (pure math, no I/O).

Takes a daily equity series and returns the standard stats a paper account / AI-arena
agent reports: total return, max drawdown, annualized Sharpe & volatility, CAGR, best/
worst day. All ``*_pct`` fields are already-percent (e.g. 12.3 == +12.3%).
"""
from __future__ import annotations

import math

from pydantic import BaseModel


class PerfMetrics(BaseModel):
    total_return_pct: float | None = None
    max_drawdown_pct: float | None = None  # positive number: 15.0 == a 15% drawdown
    sharpe: float | None = None
    cagr_pct: float | None = None
    volatility_pct: float | None = None  # annualized
    best_day_pct: float | None = None
    worst_day_pct: float | None = None


def series_metrics(equities: list[float], starting: float, *, periods_per_year: int = 252) -> PerfMetrics:
    """Compute performance stats from a daily equity series (oldest first)."""
    if not equities or starting <= 0:
        return PerfMetrics()
    last = equities[-1]
    total = (last / starting - 1) * 100

    peak = equities[0]
    max_dd = 0.0
    rets: list[float] = []
    prev = equities[0]
    for e in equities[1:]:
        if prev > 0:
            rets.append(e / prev - 1)
        prev = e
        peak = max(peak, e)
        if peak > 0:
            max_dd = max(max_dd, (peak - e) / peak)

    n = len(equities)
    years = n / periods_per_year if n else 0.0
    cagr = ((last / starting) ** (1 / years) - 1) * 100 if years > 0.05 and last > 0 else None

    mean_r = sum(rets) / len(rets) if rets else 0.0
    var = sum((r - mean_r) ** 2 for r in rets) / len(rets) if rets else 0.0
    std = math.sqrt(var)
    sharpe = (mean_r / std * math.sqrt(periods_per_year)) if std > 1e-12 else None
    vol = std * math.sqrt(periods_per_year) * 100 if std > 1e-12 else None

    return PerfMetrics(
        total_return_pct=round(total, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        sharpe=round(sharpe, 2) if sharpe is not None else None,
        cagr_pct=round(cagr, 2) if cagr is not None else None,
        volatility_pct=round(vol, 2) if vol is not None else None,
        best_day_pct=round(max(rets) * 100, 2) if rets else None,
        worst_day_pct=round(min(rets) * 100, 2) if rets else None,
    )
