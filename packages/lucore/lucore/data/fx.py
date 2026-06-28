"""FX rates for multi-currency portfolios (US/HK/A-share -> base). Uses yfinance pairs."""
from __future__ import annotations

import yfinance as yf
from cachetools import TTLCache

_cache: TTLCache = TTLCache(maxsize=64, ttl=3600)


def get_fx_rate(from_ccy: str, to_ccy: str = "USD") -> float:
    """Multiplier to convert `from_ccy` into `to_ccy`. Returns 1.0 on same ccy or failure."""
    from_ccy, to_ccy = from_ccy.upper(), to_ccy.upper()
    if from_ccy == to_ccy:
        return 1.0
    key = f"{from_ccy}{to_ccy}"
    if key in _cache:
        return _cache[key]
    rate = 1.0
    try:
        df = yf.Ticker(f"{from_ccy}{to_ccy}=X").history(period="5d", interval="1d")
        closes = [c for c in df["Close"].tolist() if c == c]
        if closes:
            rate = float(closes[-1])
    except Exception:
        rate = 1.0
    _cache[key] = rate
    return rate


def fx_map(currencies: set[str], base: str = "USD") -> dict[str, float]:
    return {c: get_fx_rate(c, base) for c in currencies}
