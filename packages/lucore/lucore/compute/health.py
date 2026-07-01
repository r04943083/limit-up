"""Deterministic watchlist health score (#D3).

A 0-100 composite over trend, momentum (RSI), trend-structure (price vs SMA200),
and 52-week range position. Pure function so it's testable and the LLM never invents it.
"""
from __future__ import annotations

from pydantic import BaseModel


class Health(BaseModel):
    score: float        # 0-100
    label: str          # strong / healthy / neutral / weak / poor
    factors: list[str]  # short human-readable contributors


def _label(score: float) -> str:
    if score >= 75:
        return "strong"
    if score >= 60:
        return "healthy"
    if score >= 45:
        return "neutral"
    if score >= 30:
        return "weak"
    return "poor"


def health_score(
    *,
    price: float | None = None,
    sma50: float | None = None,
    sma200: float | None = None,
    rsi: float | None = None,
    trend: str | None = None,
    week52_low: float | None = None,
    week52_high: float | None = None,
) -> Health:
    """Composite of four sub-scores, each 0-100, averaged over the ones we can compute."""
    parts: list[float] = []
    factors: list[str] = []

    # 1) Trend regime
    if trend == "uptrend":
        parts.append(80.0)
        factors.append("uptrend")
    elif trend == "downtrend":
        parts.append(25.0)
        factors.append("downtrend")
    elif trend:
        parts.append(50.0)

    # 2) Momentum via RSI — healthy band ~45-65, penalize overbought/oversold extremes
    if rsi is not None:
        if 45 <= rsi <= 65:
            parts.append(80.0)
        elif rsi > 75:
            parts.append(35.0)
            factors.append(f"overbought RSI {rsi:.0f}")
        elif rsi < 30:
            parts.append(35.0)
            factors.append(f"oversold RSI {rsi:.0f}")
        else:
            parts.append(60.0)

    # 3) Trend structure — price relative to the 200-day average
    if price and sma200:
        above = price >= sma200
        parts.append(75.0 if above else 35.0)
        factors.append("above 200DMA" if above else "below 200DMA")

    # 4) 52-week range position (higher = nearer highs, momentum-positive but capped)
    if price and week52_low is not None and week52_high and week52_high > week52_low:
        # Clamp to [0,1] so the sub-score stays inside its intended 40..90 band: today's price
        # can print above the *cached* 52w high (a fresh high not yet in the stored range,
        # which would push it past 90) or below the cached low (would drop it under 40).
        pos = max(0.0, min(1.0, (price - week52_low) / (week52_high - week52_low)))
        parts.append(40.0 + pos * 50.0)  # map to 40..90
        if pos >= 0.9:
            factors.append("near 52w high")
        elif pos <= 0.15:
            factors.append("near 52w low")

    score = round(sum(parts) / len(parts), 1) if parts else 50.0
    return Health(score=score, label=_label(score), factors=factors[:4])
