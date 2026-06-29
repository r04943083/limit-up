"""Intraday (分时 / 5 日) price line.

Intraday is inherently live and has many bars per day, so it does NOT go through the
date-keyed PriceBar cache (which stores one row per day). We fetch it on demand from
yfinance when the user explicitly opens the 分时/5日 view. Degrades to [] on any error.
"""
from __future__ import annotations

from pydantic import BaseModel


class IntradayPoint(BaseModel):
    t: str  # ISO timestamp
    price: float
    volume: float | None = None


# range -> (yfinance period, interval)
_RANGES: dict[str, tuple[str, str]] = {
    "1d": ("1d", "1m"),   # 分时
    "5d": ("5d", "5m"),   # 5 日
}


def get_intraday(symbol: str, rng: str = "1d") -> list[IntradayPoint]:
    period, interval = _RANGES.get(rng, _RANGES["1d"])
    try:
        import yfinance as yf

        df = yf.Ticker(symbol.upper()).history(period=period, interval=interval, auto_adjust=False)
    except Exception:  # noqa: BLE001 - network/parse hiccups degrade to empty
        return []
    out: list[IntradayPoint] = []
    for idx, row in df.iterrows():
        c = row.get("Close")
        try:
            price = float(c)
        except (TypeError, ValueError):
            continue
        if price != price:  # NaN
            continue
        t = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
        vol = row.get("Volume")
        try:
            v = float(vol)
            if v != v:
                v = None
        except (TypeError, ValueError):
            v = None
        out.append(IntradayPoint(t=t, price=price, volume=v))
    return out
