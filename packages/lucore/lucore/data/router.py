"""DataRouter — the single entry point the rest of LU uses for market data.

Routes each request to an adapter that serves the symbol's market (fallback chain),
and transparently caches daily OHLCV in SQLite.
"""
from __future__ import annotations

import datetime as dt

from ..markets import Market, infer_market
from . import cache
from .base import (
    Bar,
    CompanyProfile,
    Financials,
    Fundamentals,
    MarketDataAdapter,
    NewsItem,
    Quote,
)
from .yfinance_adapter import YFinanceAdapter


class DataRouter:
    def __init__(self, adapters: list[MarketDataAdapter] | None = None) -> None:
        # Order = priority. yfinance covers all three markets for Phase 1.
        self.adapters = adapters or [YFinanceAdapter()]

    def _for(self, market: Market) -> MarketDataAdapter:
        for a in self.adapters:
            if a.supports(market):
                return a
        raise RuntimeError(f"No data adapter for market {market}")

    def get_quote(self, symbol: str) -> Quote:
        return self._for(infer_market(symbol)).get_quote(symbol)

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        f = self._for(infer_market(symbol)).get_fundamentals(symbol)
        cache.ensure_stock(
            symbol, name=f.name, sector=f.sector, industry=f.industry, currency=f.currency
        )
        return f

    def get_news(self, symbol: str, limit: int = 10) -> list[NewsItem]:
        return self._for(infer_market(symbol)).get_news(symbol, limit=limit)

    def get_financials(self, symbol: str) -> Financials:
        try:
            return self._for(infer_market(symbol)).get_financials(symbol)
        except Exception:  # noqa: BLE001 - missing statements shouldn't break the page
            return Financials(symbol=symbol, market=infer_market(symbol))

    def get_profile(self, symbol: str) -> CompanyProfile:
        try:
            return self._for(infer_market(symbol)).get_profile(symbol)
        except Exception:  # noqa: BLE001 - missing profile shouldn't break the page
            return CompanyProfile(symbol=symbol, market=infer_market(symbol))

    def get_ohlcv(
        self, symbol: str, period: str = "1y", interval: str = "1d", refresh: bool = True
    ) -> list[Bar]:
        """Return cached bars, refreshing from the live adapter when stale/empty."""
        cache.ensure_stock(symbol)
        latest = cache.latest_cached_date(symbol, interval)
        stale = latest is None or (dt.date.today() - latest).days >= 1
        if refresh and stale:
            live = self._for(infer_market(symbol)).get_ohlcv(symbol, period=period, interval=interval)
            if live:
                cache.write_bars(symbol, interval, live)
        return cache.read_bars(symbol, interval)


# Module-level singleton for convenience.
_router: DataRouter | None = None


def get_router() -> DataRouter:
    global _router
    if _router is None:
        _router = DataRouter()
    return _router
