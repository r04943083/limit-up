"""Intraday (分时 / 5 日) price line.

Intraday is inherently live and has many bars per day, so it does NOT go through the
date-keyed PriceBar cache (which stores one row per day). We fetch it on demand from
yfinance when the user explicitly opens the 分时/5日 view. Degrades to [] on any error.

US equities trade pre-market (04:00–09:30 ET) and after-hours (16:00–20:00 ET); those
extended sessions are real signal, so we request them (`prepost=True`) and tag each point
with its session so the UI can offer an RTH/EXT toggle and style extended bars differently.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from ..markets import MARKET_TZ, Market, infer_market


class IntradayPoint(BaseModel):
    t: str  # ISO timestamp
    price: float
    volume: float | None = None
    session: str = "reg"  # pre | reg | post (regular-trading-hours vs extended)


# range -> (yfinance period, interval)
_RANGES: dict[str, tuple[str, str]] = {
    "1d": ("1d", "1m"),   # 分时
    "5d": ("5d", "5m"),   # 5 日
}

# Regular-session bounds (market-local time) per market.
_RTH: dict[Market, tuple[dt.time, dt.time]] = {
    Market.US: (dt.time(9, 30), dt.time(16, 0)),
    Market.HK: (dt.time(9, 30), dt.time(16, 0)),
    Market.CN: (dt.time(9, 30), dt.time(15, 0)),
}


def _session_of(ts, market: Market) -> str:
    """Classify a timestamp as pre / reg / post using the market-local clock."""
    open_t, close_t = _RTH.get(market, (dt.time(9, 30), dt.time(16, 0)))
    try:
        local = ts.astimezone(ZoneInfo(MARKET_TZ[market]))
        clk = local.time()
    except Exception:  # noqa: BLE001 - tz-naive or odd index → assume regular
        return "reg"
    if clk < open_t:
        return "pre"
    if clk >= close_t:
        return "post"
    return "reg"


def get_intraday(symbol: str, rng: str = "1d", prepost: bool = True) -> list[IntradayPoint]:
    period, interval = _RANGES.get(rng, _RANGES["1d"])
    market = infer_market(symbol)
    # Extended hours only apply to US; asking for prepost elsewhere is harmless but pointless.
    want_prepost = prepost and market == Market.US
    try:
        import yfinance as yf

        df = yf.Ticker(symbol.upper()).history(
            period=period, interval=interval, auto_adjust=False, prepost=want_prepost
        )
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
        session = _session_of(idx, market) if want_prepost else "reg"
        out.append(IntradayPoint(t=t, price=price, volume=v, session=session))
    return out
