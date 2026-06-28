"""Deterministic category screener. Pure functions over a metrics dict, so the LLM
only scores/justifies the candidates Python pre-selected (never picks from thin air).
"""
from __future__ import annotations

from pydantic import BaseModel

CATEGORIES = ["growth", "value", "momentum", "dividend", "ai", "quality", "swing"]

# Curated AI/semis theme membership (extend over time / move to DB later).
AI_THEME = {
    "NVDA", "AMD", "AVGO", "TSM", "MU", "ASML", "SMCI", "MRVL", "ARM", "PLTR",
    "MSFT", "GOOGL", "META", "AMZN", "TSLA", "CRWD", "SNOW", "0700.HK", "9988.HK",
}


class ScreenInput(BaseModel):
    symbol: str
    name: str | None = None
    sector: str | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    ps: float | None = None
    peg: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    trend: str | None = None
    rsi: float | None = None
    price: float | None = None
    sma50: float | None = None
    sma200: float | None = None


class Candidate(BaseModel):
    symbol: str
    name: str | None
    category: str
    rank_value: float
    reasons: list[str]


def _rule(c: ScreenInput, category: str) -> tuple[bool, float, list[str]] | None:
    """Return (passes, rank_value, reasons) or None if data is insufficient."""
    if category == "value":
        if c.pe_ttm is None or c.pe_ttm <= 0:
            return None
        ok = c.pe_ttm <= 22 and (c.pb is None or c.pb <= 4)
        return ok, -c.pe_ttm, [f"P/E {c.pe_ttm:.1f}"] + ([f"P/B {c.pb:.1f}"] if c.pb else [])
    if category == "growth":
        if c.revenue_growth is None:
            return None
        ok = c.revenue_growth >= 0.15
        return ok, c.revenue_growth, [f"Rev growth {c.revenue_growth*100:.0f}%"]
    if category == "momentum":
        if c.trend is None or c.rsi is None:
            return None
        strength = (c.price / c.sma200 - 1) if (c.price and c.sma200) else 0.0
        ok = c.trend == "uptrend" and 50 <= c.rsi <= 78
        return ok, strength, ["Uptrend", f"RSI {c.rsi:.0f}"]
    if category == "dividend":
        if c.dividend_yield is None:
            return None
        ok = c.dividend_yield >= 0.025
        return ok, c.dividend_yield, [f"Yield {c.dividend_yield*100:.1f}%"]
    if category == "ai":
        ok = c.symbol in AI_THEME
        return ok, (c.revenue_growth or 0.0), ["AI/semis theme"]
    if category == "quality":
        if c.roe is None or c.net_margin is None:
            return None
        ok = c.roe >= 0.15 and c.net_margin >= 0.12
        score = (c.roe or 0) + (c.net_margin or 0)
        return ok, score, [f"ROE {c.roe*100:.0f}%", f"Net margin {c.net_margin*100:.0f}%"]
    if category == "swing":
        if c.rsi is None:
            return None
        ok = c.rsi <= 42 and c.trend != "downtrend"
        return ok, -c.rsi, [f"RSI {c.rsi:.0f} (oversold-ish)"]
    return None


def screen(category: str, inputs: list[ScreenInput], top_n: int = 6) -> list[Candidate]:
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category}")
    out: list[Candidate] = []
    for c in inputs:
        res = _rule(c, category)
        if res is None:
            continue
        ok, rank, reasons = res
        if ok:
            out.append(Candidate(symbol=c.symbol, name=c.name, category=category, rank_value=rank, reasons=reasons))
    out.sort(key=lambda x: -x.rank_value)
    return out[:top_n]
