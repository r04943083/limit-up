"""Performance tear-sheet: the rigorous risk/return stats a professional report shows
(Sharpe / Sortino / Calmar, drawdown, VaR/CVaR, win-rate, monthly-returns heatmap, and
optional benchmark alpha/beta). Pure deterministic math over a dated equity series — no
plotting/library dependency, so the numbers stay first-class compute output the LLM only
narrates.

All ``*_pct`` fields are already-percent (12.3 == +12.3%). Drawdown is reported positive.
"""
from __future__ import annotations

import datetime as dt
import math

from pydantic import BaseModel


class MonthReturn(BaseModel):
    month: str          # YYYY-MM
    return_pct: float


class Tearsheet(BaseModel):
    n_days: int = 0
    total_return_pct: float | None = None
    cagr_pct: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    volatility_pct: float | None = None      # annualized
    max_drawdown_pct: float | None = None     # positive
    var95_pct: float | None = None            # daily 95% Value-at-Risk (positive loss)
    cvar95_pct: float | None = None           # daily 95% Conditional VaR (positive loss)
    win_rate_pct: float | None = None
    avg_win_pct: float | None = None
    avg_loss_pct: float | None = None
    profit_factor: float | None = None        # Σ gains / Σ|losses|
    best_day_pct: float | None = None
    worst_day_pct: float | None = None
    best_month_pct: float | None = None
    worst_month_pct: float | None = None
    monthly_returns: list[MonthReturn] = []
    # Benchmark comparison (optional)
    benchmark_return_pct: float | None = None
    alpha_pct: float | None = None            # annualized Jensen's alpha
    beta: float | None = None


def _returns(equities: list[float]) -> list[float]:
    out: list[float] = []
    prev = equities[0]
    for e in equities[1:]:
        if prev > 0:
            out.append(e / prev - 1)
        prev = e
    return out


def _std(xs: list[float], mean: float) -> float:
    if not xs:
        return 0.0
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))


def _percentile(sorted_xs: list[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted list (q in [0,1])."""
    if not sorted_xs:
        return 0.0
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = q * (len(sorted_xs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_xs[lo]
    frac = pos - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


def _monthly_returns(dates: list[dt.date], equities: list[float]) -> list[MonthReturn]:
    """Month-end-to-month-end returns from a dated equity series."""
    if len(dates) != len(equities) or not dates:
        return []
    # Last equity value observed in each calendar month (month-end mark).
    month_last: dict[str, float] = {}
    order: list[str] = []
    for d, e in zip(dates, equities):
        key = f"{d.year:04d}-{d.month:02d}"
        if key not in month_last:
            order.append(key)
        month_last[key] = e
    out: list[MonthReturn] = []
    prev = None
    for key in order:
        cur = month_last[key]
        if prev is not None and prev > 0:
            out.append(MonthReturn(month=key, return_pct=round((cur / prev - 1) * 100, 2)))
        prev = cur
    return out


def tearsheet(
    dates: list[dt.date],
    equities: list[float],
    starting: float,
    *,
    benchmark: list[float] | None = None,
    periods_per_year: int = 252,
) -> Tearsheet:
    """Full tear-sheet from a dated daily equity series (oldest first). ``benchmark`` is an
    aligned equity series for the same dates (e.g. SPY) used for alpha/beta."""
    if not equities or starting <= 0 or len(dates) != len(equities):
        return Tearsheet(n_days=len(equities))

    last = equities[-1]
    total = (last / starting - 1) * 100
    rets = _returns(equities)
    n = len(equities)
    years = n / periods_per_year

    # Drawdown
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        peak = max(peak, e)
        if peak > 0:
            max_dd = max(max_dd, (peak - e) / peak)

    mean_r = sum(rets) / len(rets) if rets else 0.0
    std = _std(rets, mean_r)
    # Downside deviation: sqrt(Σ min(r,0)² / N) — divide by the TOTAL period count N (Sortino's
    # definition, matching empyrical), NOT by the number of losing days.
    dstd = math.sqrt(sum(min(r, 0.0) ** 2 for r in rets) / len(rets)) if rets else 0.0

    sharpe = (mean_r / std * math.sqrt(periods_per_year)) if std > 1e-12 else None
    sortino = (mean_r / dstd * math.sqrt(periods_per_year)) if dstd > 1e-12 else None
    vol = std * math.sqrt(periods_per_year) * 100 if std > 1e-12 else None
    cagr = ((last / starting) ** (1 / years) - 1) * 100 if years > 0.05 and last > 0 else None
    calmar = (cagr / (max_dd * 100)) if (cagr is not None and max_dd > 1e-9) else None

    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r < 0]
    win_rate = len(wins) / len(rets) * 100 if rets else None
    avg_win = sum(wins) / len(wins) * 100 if wins else None
    avg_loss = sum(losses) / len(losses) * 100 if losses else None
    gain_sum = sum(wins)
    loss_sum = -sum(losses)
    profit_factor = (gain_sum / loss_sum) if loss_sum > 1e-12 else None

    srt = sorted(rets)
    var95 = -_percentile(srt, 0.05) * 100 if srt else None  # positive loss magnitude
    tail = [r for r in srt if r <= _percentile(srt, 0.05)]
    cvar95 = -(sum(tail) / len(tail)) * 100 if tail else None

    months = _monthly_returns(dates, equities)
    mvals = [m.return_pct for m in months]

    ts = Tearsheet(
        n_days=n,
        total_return_pct=round(total, 2),
        cagr_pct=round(cagr, 2) if cagr is not None else None,
        sharpe=round(sharpe, 2) if sharpe is not None else None,
        sortino=round(sortino, 2) if sortino is not None else None,
        calmar=round(calmar, 2) if calmar is not None else None,
        volatility_pct=round(vol, 2) if vol is not None else None,
        max_drawdown_pct=round(max_dd * 100, 2),
        var95_pct=round(var95, 2) if var95 is not None else None,
        cvar95_pct=round(cvar95, 2) if cvar95 is not None else None,
        win_rate_pct=round(win_rate, 2) if win_rate is not None else None,
        avg_win_pct=round(avg_win, 2) if avg_win is not None else None,
        avg_loss_pct=round(avg_loss, 2) if avg_loss is not None else None,
        profit_factor=round(profit_factor, 2) if profit_factor is not None else None,
        best_day_pct=round(max(rets) * 100, 2) if rets else None,
        worst_day_pct=round(min(rets) * 100, 2) if rets else None,
        best_month_pct=round(max(mvals), 2) if mvals else None,
        worst_month_pct=round(min(mvals), 2) if mvals else None,
        monthly_returns=months,
    )

    if benchmark and len(benchmark) == len(equities) and benchmark[0] > 0:
        ts.benchmark_return_pct = round((benchmark[-1] / benchmark[0] - 1) * 100, 2)
        b_rets = _returns(benchmark)
        m = min(len(rets), len(b_rets))
        if m >= 2:
            pr, pb = rets[-m:], b_rets[-m:]
            mb = sum(pb) / m
            var_b = sum((x - mb) ** 2 for x in pb) / m
            if var_b > 1e-12:
                mr = sum(pr) / m
                cov = sum((pr[i] - mr) * (pb[i] - mb) for i in range(m)) / m
                beta = cov / var_b
                ts.beta = round(beta, 2)
                # Annualized Jensen's alpha (rf=0): (mean_p - beta*mean_b) per period.
                ts.alpha_pct = round((mr - beta * mb) * periods_per_year * 100, 2)
    return ts
