"""Deterministic valuation models. The LLM may narrate these numbers but never computes them.

Currently: a simple, transparent DCF (discounted free cash flow) with an explicit
projection + Gordon terminal value, so the assumptions are auditable in the UI.
"""
from __future__ import annotations

import datetime as dt
from statistics import mean, median

from pydantic import BaseModel


class DcfYear(BaseModel):
    year: int
    fcf: float
    pv: float


class DcfResult(BaseModel):
    # Assumptions echoed back (so the UI shows exactly what produced the number)
    fcf_base: float
    growth: float
    discount: float
    terminal_growth: float
    years: int
    shares: float | None = None
    net_debt: float = 0.0
    # Outputs
    pv_explicit: float = 0.0
    terminal_value: float = 0.0
    pv_terminal: float = 0.0
    enterprise_value: float = 0.0
    equity_value: float = 0.0
    intrinsic_per_share: float | None = None
    table: list[DcfYear] = []


def dcf(
    fcf_base: float,
    growth: float = 0.08,
    discount: float = 0.09,
    terminal_growth: float = 0.025,
    years: int = 5,
    shares: float | None = None,
    net_debt: float = 0.0,
) -> DcfResult:
    """Two-stage DCF.

    Stage 1: grow ``fcf_base`` at ``growth`` for ``years``, discount each year at ``discount``.
    Stage 2: Gordon terminal value on the final-year FCF, discounted back.
    Equity = enterprise value − net debt; per-share = equity / shares.
    """
    years = max(1, int(years))
    # Clamp terminal_growth below discount or the Gordon model blows up / goes negative.
    if terminal_growth >= discount:
        terminal_growth = discount - 0.01

    table: list[DcfYear] = []
    pv_explicit = 0.0
    fcf = fcf_base
    for yr in range(1, years + 1):
        fcf = fcf * (1.0 + growth)
        pv = fcf / (1.0 + discount) ** yr
        pv_explicit += pv
        table.append(DcfYear(year=yr, fcf=fcf, pv=pv))

    terminal_value = fcf * (1.0 + terminal_growth) / (discount - terminal_growth)
    pv_terminal = terminal_value / (1.0 + discount) ** years
    enterprise_value = pv_explicit + pv_terminal
    equity_value = enterprise_value - (net_debt or 0.0)
    intrinsic_per_share = equity_value / shares if shares else None

    return DcfResult(
        fcf_base=fcf_base, growth=growth, discount=discount,
        terminal_growth=terminal_growth, years=years, shares=shares, net_debt=net_debt or 0.0,
        pv_explicit=pv_explicit, terminal_value=terminal_value, pv_terminal=pv_terminal,
        enterprise_value=enterprise_value, equity_value=equity_value,
        intrinsic_per_share=intrinsic_per_share, table=table,
    )


# ────────────────────────────── Valuation bands (历史估值带) ──────────────────────────────
# Futu's 分析 tab shows a PE/PB/PS *band*: the ratio's history, its mean ("平均水平"),
# range, and where today sits (percentile). We rebuild it deterministically from cached
# daily closes ÷ a stepwise per-share denominator (TTM EPS / BVPS / TTM SPS), forward-
# filled from each reported quarter. The LLM never touches these numbers.


class RatioPoint(BaseModel):
    date: dt.date
    value: float


class ValuationBand(BaseModel):
    metric: str  # "PE" | "PB" | "PS"
    points: list[RatioPoint] = []
    current: float | None = None
    mean: float | None = None
    median: float | None = None
    low: float | None = None
    high: float | None = None
    percentile: float | None = None  # current's rank within history, 0..100 (低=便宜)


class PerSharePoint(BaseModel):
    """A per-share denominator effective from ``date`` onward (a reported quarter)."""
    date: dt.date
    value: float


def parse_period(label: str) -> dt.date | None:
    """Parse a statement period label → the period-end date.
    Annual ``"2024"`` → Dec-31; quarterly ``"2024-03"`` → that month's end."""
    label = (label or "").strip()
    try:
        if len(label) == 4:
            return dt.date(int(label), 12, 31)
        parts = label.split("-")
        y, m = int(parts[0]), int(parts[1])
        if m >= 12:
            return dt.date(y, 12, 31)
        return dt.date(y, m + 1, 1) - dt.timedelta(days=1)
    except Exception:  # noqa: BLE001 - malformed label → unusable point
        return None


def ttm(values_oldest_first: list[float | None]) -> list[float | None]:
    """Rolling 4-period (trailing-twelve-month) sum. ``None`` until 4 valid points exist
    in the window (or any window value is missing)."""
    out: list[float | None] = []
    for i in range(len(values_oldest_first)):
        if i < 3:
            out.append(None)
            continue
        window = values_oldest_first[i - 3 : i + 1]
        out.append(sum(window) if all(v is not None for v in window) else None)
    return out


def valuation_band(
    metric: str,
    closes: list[tuple[dt.date, float]],
    per_share: list[PerSharePoint],
    *,
    current: float | None = None,
) -> ValuationBand:
    """Build a ratio band: for each daily close, ratio = close ÷ (per-share value in effect
    that day, forward-filled from the latest reported quarter ≤ that date). Positive ratios
    only (negative earnings have no meaningful PE). ``current`` overrides the last point with
    the live ratio when provided."""
    pts = sorted([p for p in per_share if p.value and p.value > 0], key=lambda p: p.date)
    band = ValuationBand(metric=metric)
    if not pts or not closes:
        band.current = current
        return band

    rows = sorted(closes, key=lambda c: c[0])
    out: list[RatioPoint] = []
    j = 0
    cur_val: float | None = None
    for d, close in rows:
        while j < len(pts) and pts[j].date <= d:
            cur_val = pts[j].value
            j += 1
        if cur_val and cur_val > 0 and close > 0:
            out.append(RatioPoint(date=d, value=round(close / cur_val, 4)))

    if not out:
        band.current = current
        return band

    vals = [p.value for p in out]
    band.points = out
    band.current = current if current is not None else vals[-1]
    band.mean = round(mean(vals), 4)
    band.median = round(median(vals), 4)
    band.low = min(vals)
    band.high = max(vals)
    if band.current is not None:
        below = sum(1 for v in vals if v <= band.current)
        band.percentile = round(below / len(vals) * 100.0, 1)
    return band


def implied_growth_from_fcf(fcf_newest_first: list[float | None]) -> float | None:
    """Estimate a forward growth rate from the FCF history via CAGR (oldest→newest),
    clamped to a sane band. ``fcf_newest_first`` is the series as stored (newest first)."""
    series = [v for v in fcf_newest_first if v is not None]
    if len(series) < 2:
        return None
    newest, oldest = series[0], series[-1]
    n = len(series) - 1
    if oldest is None or oldest <= 0 or newest <= 0:
        return None
    cagr = (newest / oldest) ** (1.0 / n) - 1.0
    return max(-0.05, min(0.25, cagr))
