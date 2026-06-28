"""Deterministic valuation models. The LLM may narrate these numbers but never computes them.

Currently: a simple, transparent DCF (discounted free cash flow) with an explicit
projection + Gordon terminal value, so the assumptions are auditable in the UI.
"""
from __future__ import annotations

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
