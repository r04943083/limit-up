"""Data-source contracts. Everything reads through MarketDataAdapter so providers
(yfinance now; Finnhub/akshare/futu later) are swappable without touching call sites.
"""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod

from pydantic import BaseModel

from ..markets import Market


class Quote(BaseModel):
    symbol: str
    market: Market
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    currency: str | None = None
    name: str | None = None
    as_of: dt.datetime | None = None


class Bar(BaseModel):
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class Fundamentals(BaseModel):
    symbol: str
    market: Market
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    # Valuation
    market_cap: float | None = None
    enterprise_value: float | None = None
    pe_ttm: float | None = None
    pe_fwd: float | None = None
    pb: float | None = None
    ps: float | None = None
    peg: float | None = None
    ev_ebitda: float | None = None
    # Profitability
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    roa: float | None = None
    # Growth / per-share
    revenue: float | None = None
    revenue_growth: float | None = None
    eps: float | None = None
    earnings_growth: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    # Trading stats
    beta: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    shares_outstanding: float | None = None
    float_shares: float | None = None
    short_percent: float | None = None
    avg_volume: float | None = None
    # Analyst consensus
    recommendation: str | None = None
    recommendation_mean: float | None = None  # 1=Strong Buy … 5=Sell (Futu-style gauge)
    num_analysts: int | None = None
    target_mean: float | None = None
    target_high: float | None = None
    target_low: float | None = None
    target_median: float | None = None


class NewsItem(BaseModel):
    title: str
    publisher: str | None = None
    url: str | None = None
    published_at: dt.datetime | None = None


class StatementRow(BaseModel):
    """One financial-statement line item across periods (aligned to Statement.periods)."""
    label: str
    values: list[float | None] = []


class Statement(BaseModel):
    """A financial statement as a table: period columns (newest-first) × labeled rows."""
    periods: list[str] = []  # column headers, e.g. ["2024", "2023", ...]
    rows: list[StatementRow] = []


class Financials(BaseModel):
    """Curated financial statements (annual + quarterly) for the deep-research page,
    plus the few derived figures a DCF needs. Defensive: missing data degrades to empty."""
    symbol: str
    market: Market
    currency: str | None = None
    income: Statement = Statement()
    balance: Statement = Statement()
    cashflow: Statement = Statement()
    income_q: Statement = Statement()
    balance_q: Statement = Statement()
    cashflow_q: Statement = Statement()
    # Derived (annual, newest-first) for valuation
    fcf_periods: list[str] = []
    fcf: list[float | None] = []
    shares: float | None = None
    cash: float | None = None
    total_debt: float | None = None
    net_debt: float | None = None


class Dividend(BaseModel):
    """One cash dividend (ex-date + per-share amount)."""
    ex_date: dt.date
    amount: float


class HolderRow(BaseModel):
    """One institutional / fund holder line."""
    name: str
    pct: float | None = None       # share of outstanding, as a fraction (0.05 = 5%)
    shares: float | None = None
    value: float | None = None
    date_reported: dt.date | None = None


class CompanyProfile(BaseModel):
    """Company overview + dividends + ownership for the deep-research page.
    Defensive: every field degrades to None / empty rather than raising."""
    symbol: str
    market: Market
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    employees: int | None = None
    summary: str | None = None       # long business description
    currency: str | None = None
    # Dividends (newest-first)
    dividends: list[Dividend] = []
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    # Ownership
    insiders_pct: float | None = None
    institutions_pct: float | None = None
    top_institutions: list[HolderRow] = []


class MarketDataAdapter(ABC):
    """A pluggable market-data source. Implementations should be defensive: return
    None / empty rather than raising on missing fields, and declare which markets they serve.
    """

    name: str = "base"
    markets: tuple[Market, ...] = ()

    def supports(self, market: Market) -> bool:
        return market in self.markets

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def get_ohlcv(self, symbol: str, period: str = "1y", interval: str = "1d") -> list[Bar]: ...

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> Fundamentals: ...

    @abstractmethod
    def get_news(self, symbol: str, limit: int = 10) -> list[NewsItem]: ...

    @abstractmethod
    def get_financials(self, symbol: str) -> Financials: ...

    @abstractmethod
    def get_profile(self, symbol: str) -> CompanyProfile: ...
