"""Valuation service: assembles Futu-style 历史估值带 (PE / PB / PS bands) + the analyst
consensus for the 自选「分析」right panel.

Bands are rebuilt deterministically from cached daily closes ÷ a stepwise per-share
denominator derived from the reported quarterly statements (TTM EPS / TTM sales-per-share /
book-value-per-share). The LLM never touches these numbers — pure compute over cached data.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..compute.valuation import PerSharePoint, ValuationBand, parse_period, ttm, valuation_band
from ..data.base import Statement
from ..data.cache import read_bars
from .financials import get_financials_cached
from .research import get_research

# Statement row labels (set in the yfinance adapter's _INCOME_ROWS / _BALANCE_ROWS).
_EPS_LABEL = "摊薄EPS"
_REVENUE_LABEL = "营业收入"
_EQUITY_LABEL = "股东权益"


class AnalystConsensus(BaseModel):
    recommendation: str | None = None         # yfinance key, e.g. "strong_buy"
    recommendation_mean: float | None = None  # 1=强力买入 … 5=卖出
    num_analysts: int | None = None
    price: float | None = None
    target_mean: float | None = None
    target_high: float | None = None
    target_low: float | None = None
    target_median: float | None = None
    upside_pct: float | None = None           # (target_mean − price) / price × 100


class ValuationOut(BaseModel):
    symbol: str
    currency: str | None = None
    pe: ValuationBand
    pb: ValuationBand
    ps: ValuationBand
    analyst: AnalystConsensus


def _row_oldest_first(stmt: Statement, label: str) -> tuple[list[str], list[float | None]]:
    """Return (period labels, values) for a statement row, reordered oldest-first.
    Statements are stored newest-first; bands need chronological order."""
    for r in stmt.rows:
        if r.label == label:
            n = min(len(stmt.periods), len(r.values))
            periods = list(reversed(stmt.periods[:n]))
            values = list(reversed(r.values[:n]))
            return periods, values
    return [], []


def _points_from_ttm(stmt: Statement, label: str, *, divide_by: float | None = None) -> list[PerSharePoint]:
    """Per-share points from a *flow* line (EPS already per-share; revenue needs ÷ shares):
    rolling-TTM, then keyed to each quarter's period-end date."""
    periods, values = _row_oldest_first(stmt, label)
    if not periods:
        return []
    series = ttm(values)
    pts: list[PerSharePoint] = []
    for label_p, v in zip(periods, series):
        if v is None:
            continue
        d = parse_period(label_p)
        per_share = v / divide_by if divide_by else v
        if d is not None and per_share and per_share > 0:
            pts.append(PerSharePoint(date=d, value=per_share))
    return pts


def _points_direct(stmt: Statement, label: str, *, divide_by: float | None = None) -> list[PerSharePoint]:
    """Per-share points with no TTM sum — for stock lines (equity, point-in-time) and for
    *annual* flow lines (annual EPS/revenue is already a trailing-twelve-month figure at
    fiscal year-end). ``divide_by`` converts a total (revenue/equity) to per-share."""
    periods, values = _row_oldest_first(stmt, label)
    pts: list[PerSharePoint] = []
    for label_p, v in zip(periods, values):
        if v is None:
            continue
        per_share = (v / divide_by) if divide_by else v
        d = parse_period(label_p)
        if d is not None and per_share and per_share > 0:
            pts.append(PerSharePoint(date=d, value=per_share))
    return pts


def get_valuation(symbol: str) -> ValuationOut:
    sym = symbol.strip().upper()
    rb = get_research(sym)  # cache-first: current quote + fundamentals
    fund = rb.fundamentals
    fin = get_financials_cached(sym)
    shares = fin.shares or fund.shares_outstanding

    closes = [(b.date, b.close) for b in read_bars(sym, "1d") if b.close and b.close > 0]

    # Quarterly-only: rebuild trailing-twelve-month EPS / sales-per-share from the reported
    # quarters, and book-value-per-share from quarterly equity. Annual figures are NOT blended
    # in — a fiscal-year EPS forward-filled across the following calendar year (before the next
    # report) pins a stale denominator onto newer prices and inflates the ratio. Correct over
    # long: the band spans whatever the cached quarters support (see points[].date range).
    eps_pts = _points_from_ttm(fin.income_q, _EPS_LABEL)
    sps_pts = _points_from_ttm(fin.income_q, _REVENUE_LABEL, divide_by=shares)
    bvps_pts = _points_direct(fin.balance_q, _EQUITY_LABEL, divide_by=shares)

    pe = valuation_band("PE", closes, eps_pts, current=fund.pe_ttm)
    pb = valuation_band("PB", closes, bvps_pts, current=fund.pb)
    ps = valuation_band("PS", closes, sps_pts, current=fund.ps)

    price = rb.quote.price
    tgt = fund.target_mean
    upside = ((tgt - price) / price * 100.0) if (tgt and price) else None
    analyst = AnalystConsensus(
        recommendation=fund.recommendation,
        recommendation_mean=fund.recommendation_mean,
        num_analysts=fund.num_analysts,
        price=price,
        target_mean=fund.target_mean,
        target_high=fund.target_high,
        target_low=fund.target_low,
        target_median=fund.target_median,
        upside_pct=upside,
    )
    return ValuationOut(symbol=sym, currency=fin.currency or fund.currency,
                        pe=pe, pb=pb, ps=ps, analyst=analyst)
