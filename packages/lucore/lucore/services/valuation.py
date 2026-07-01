"""Valuation service: assembles Futu-style 历史估值带 (PE / PB / PS bands) + the analyst
consensus for the 自选「分析」right panel.

Bands are rebuilt deterministically from cached daily closes ÷ a stepwise per-share
denominator derived from the reported quarterly statements (TTM EPS / TTM sales-per-share /
book-value-per-share). The LLM never touches these numbers — pure compute over cached data.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel

from ..compute.valuation import PerSharePoint, ValuationBand, parse_period, ttm, valuation_band
from ..data.base import Statement
from ..data.cache import read_bars
from ..data.router import get_router
from ..db import session_scope
from ..db.models import MarketDataCache
from .financials import get_financials_cached
from .peers import industry_average
from .research import get_research

# Analyst rating distribution shifts slowly; cache it a day so 分析 stays cache-first.
_RECSUM_TTL_HOURS = 24


def _recommendation_distribution(symbol: str) -> dict[str, int] | None:
    """Cached strongBuy/buy/hold/sell/strongSell counts for the 分析 rating bars."""
    key = f"recsum:{symbol.upper()}"
    now = dt.datetime.now(dt.timezone.utc)
    with session_scope() as s:
        row = s.get(MarketDataCache, key)
        if row is not None:
            fetched = row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=dt.timezone.utc)
            if (now - fetched).total_seconds() < _RECSUM_TTL_HOURS * 3600:
                try:
                    return json.loads(row.payload_json) or None
                except ValueError:
                    pass
    try:
        dist = get_router().get_recommendation_summary(symbol)
    except Exception:  # noqa: BLE001 - missing/old yfinance shape shouldn't break 分析
        dist = None
    if dist is None:
        return None
    payload = json.dumps(dist)
    with session_scope() as s:
        row = s.get(MarketDataCache, key)
        if row is None:
            s.add(MarketDataCache(cache_key=key, payload_json=payload, fetched_at=now))
        else:
            row.payload_json = payload
            row.fetched_at = now
    return dist

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
    # Rating distribution (Futu 买入/持有/卖出 bars). None when the source has no breakdown.
    strong_buy: int | None = None
    buy: int | None = None
    hold: int | None = None
    sell: int | None = None
    strong_sell: int | None = None


class IndustryAvg(BaseModel):
    pe: float | None = None
    pb: float | None = None
    ps: float | None = None
    peers: int = 0


class ValuationOut(BaseModel):
    symbol: str
    currency: str | None = None
    pe: ValuationBand
    pb: ValuationBand
    ps: ValuationBand
    analyst: AnalystConsensus
    industry: str | None = None
    industry_avg: IndustryAvg = IndustryAvg()
    short_percent: float | None = None  # 空头占流通股比例 (卖空数据)


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
    # EPS is already per-share. Sales-/book-per-share need ÷ shares — if shares outstanding
    # is unknown, DON'T fall back to the raw total (that builds a band from close÷total-revenue,
    # ≈0, and makes the 分位 meaningless). Leave those bands empty instead.
    eps_pts = _points_from_ttm(fin.income_q, _EPS_LABEL)
    sps_pts = _points_from_ttm(fin.income_q, _REVENUE_LABEL, divide_by=shares) if shares else []
    bvps_pts = _points_direct(fin.balance_q, _EQUITY_LABEL, divide_by=shares) if shares else []

    pe = valuation_band("PE", closes, eps_pts, current=fund.pe_ttm)
    pb = valuation_band("PB", closes, bvps_pts, current=fund.pb)
    ps = valuation_band("PS", closes, sps_pts, current=fund.ps)

    price = rb.quote.price
    tgt = fund.target_mean
    upside = ((tgt - price) / price * 100.0) if (tgt and price) else None
    dist = _recommendation_distribution(sym)
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
        **(dist or {}),
    )

    ind = industry_average(sym)
    industry_avg = IndustryAvg(pe=ind.pe, pb=ind.pb, ps=ind.ps, peers=ind.n) if ind else IndustryAvg()

    return ValuationOut(
        symbol=sym, currency=fin.currency or fund.currency,
        pe=pe, pb=pb, ps=ps, analyst=analyst,
        industry=ind.industry if ind else fund.industry,
        industry_avg=industry_avg,
        short_percent=fund.short_percent,
    )
