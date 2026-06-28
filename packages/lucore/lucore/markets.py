"""Market-aware abstraction. LU covers US + HK + A-share from the start."""
from __future__ import annotations

from enum import StrEnum


class Market(StrEnum):
    US = "US"
    HK = "HK"
    CN = "CN"  # A-share (Shanghai/Shenzhen)


# Default trading currency per market.
MARKET_CURRENCY: dict[Market, str] = {
    Market.US: "USD",
    Market.HK: "HKD",
    Market.CN: "CNY",
}

# IANA timezone per market (for trading-calendar / session logic).
MARKET_TZ: dict[Market, str] = {
    Market.US: "America/New_York",
    Market.HK: "Asia/Hong_Kong",
    Market.CN: "Asia/Shanghai",
}


def infer_market(symbol: str) -> Market:
    """Best-effort market inference from a ticker.

    Conventions: ``700.HK`` / ``0700.HK`` -> HK; ``600519.SS`` / ``000001.SZ`` -> CN;
    plain alpha tickers (``NVDA``) -> US.
    """
    s = symbol.strip().upper()
    if s.endswith(".HK"):
        return Market.HK
    if s.endswith((".SS", ".SZ", ".SH")):
        return Market.CN
    head = s.split(".")[0]
    if head.isdigit():
        # 6-digit numeric -> A-share; 1-5 digit numeric -> HK.
        return Market.CN if len(head) == 6 else Market.HK
    return Market.US
