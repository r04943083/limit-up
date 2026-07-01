"""US market-breadth feeds via yfinance's predefined Yahoo screeners (market movers).

These are the US analogue of the A-share limit-up pool / dragon-tiger board: market-wide
discovery lists, not per-symbol data, so (like cn_market) they live outside MarketDataAdapter.
Every number here comes straight from the data source or is a deterministic ratio computed in
Python — the LLM never fabricates any of it.

Yahoo's predefined screeners can rate-limit or shift schema, so fetching is defensive: a
missing field degrades to None; a hard failure raises and the caller (service) catches it.
"""
from __future__ import annotations

from pydantic import BaseModel

# Curated equity feeds (kind -> Chinese label). Order = display order on the 发现 page.
US_FEEDS: dict[str, str] = {
    "day_gainers": "涨幅榜",
    "day_losers": "跌幅榜",
    "most_actives": "成交活跃",
    "small_cap_gainers": "小盘急涨",
    "most_shorted_stocks": "高做空",
    "undervalued_growth_stocks": "低估成长",
}


class MoverStock(BaseModel):
    symbol: str
    name: str | None = None
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None       # 涨跌幅 %
    volume: float | None = None
    avg_volume: float | None = None
    market_cap: float | None = None
    pe: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    # Deterministic derived signals (computed here, not by the LLM):
    vol_ratio: float | None = None        # volume / avg_volume — "异常放量" > 1
    from_high_pct: float | None = None     # (price-52wHigh)/52wHigh*100 — 0 = at new high


class MoversBoard(BaseModel):
    kind: str
    label: str
    count: int = 0
    stocks: list[MoverStock] = []


def _num(v) -> float | None:  # noqa: ANN001
    try:
        f = float(v)
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None


def _row(q: dict) -> MoverStock | None:
    sym = q.get("symbol")
    if not sym:
        return None
    price = _num(q.get("regularMarketPrice"))
    vol = _num(q.get("regularMarketVolume"))
    avgv = _num(q.get("averageDailyVolume3Month")) or _num(q.get("averageDailyVolume10Day"))
    hi = _num(q.get("fiftyTwoWeekHigh"))
    vol_ratio = round(vol / avgv, 2) if (vol and avgv) else None
    from_high = round((price - hi) / hi * 100, 2) if (price and hi) else None
    return MoverStock(
        symbol=str(sym).upper(),
        name=q.get("shortName") or q.get("longName"),
        price=price,
        change=_num(q.get("regularMarketChange")),
        change_pct=_num(q.get("regularMarketChangePercent")),
        volume=vol,
        avg_volume=avgv,
        market_cap=_num(q.get("marketCap")),
        pe=_num(q.get("trailingPE")),
        week52_high=hi,
        week52_low=_num(q.get("fiftyTwoWeekLow")),
        vol_ratio=vol_ratio,
        from_high_pct=from_high,
    )


def fetch_movers(kind: str, count: int = 30) -> MoversBoard:
    """Fetch one predefined Yahoo movers list, normalized to MoversBoard."""
    if kind not in US_FEEDS:
        raise ValueError(f"unknown US feed: {kind}")
    import yfinance as yf

    res = yf.screen(kind, count=count)
    quotes = res.get("quotes", []) if isinstance(res, dict) else (res or [])
    stocks = [r for q in quotes if isinstance(q, dict) and (r := _row(q)) is not None]
    return MoversBoard(kind=kind, label=US_FEEDS[kind], count=len(stocks), stocks=stocks)
