"""Deterministic technical indicators, computed locally from OHLCV.

Pure pandas/numpy (no TA-Lib dependency yet). The LLM never computes these — it only
narrates them. Output arrays are aligned to the input bar dates, with NaN -> None so
the values serialize cleanly to JSON for the chart.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel

from ..data.base import Bar


class TechnicalAnalysis(BaseModel):
    dates: list[str]
    sma20: list[float | None]
    sma50: list[float | None]
    sma200: list[float | None]
    ema12: list[float | None]
    ema26: list[float | None]
    bb_upper: list[float | None]
    bb_lower: list[float | None]
    rsi14: list[float | None]
    macd: list[float | None]
    macd_signal: list[float | None]
    macd_hist: list[float | None]
    atr14: list[float | None]
    vwap: list[float | None]
    kdj_k: list[float | None] = []
    kdj_d: list[float | None] = []
    kdj_j: list[float | None] = []
    latest: dict[str, float | None]
    trend: str
    signals: list[str]


def _clean(series: pd.Series) -> list[float | None]:
    return [None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v) for v in series]


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(loss != 0, 100.0)  # no losses over the window -> RSI 100
    rsi = rsi.where(~((gain == 0) & (loss == 0)), 50.0)  # perfectly flat -> neutral 50
    return rsi


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def compute_technical(bars: list[Bar]) -> TechnicalAnalysis:
    df = pd.DataFrame(
        {
            "date": [b.date.isoformat() for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume or 0.0 for b in bars],
        }
    )
    c = df["close"]

    sma20, sma50, sma200 = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal
    bb_mid = sma20
    bb_std = c.rolling(20).std()
    bb_upper, bb_lower = bb_mid + 2 * bb_std, bb_mid - 2 * bb_std
    rsi = _rsi(c)
    atr = _atr(df)
    # KDJ (9,3,3): RSV -> K (EMA) -> D (EMA) -> J = 3K - 2D. Futu's default lower study.
    low9 = df["low"].rolling(9).min()
    high9 = df["high"].rolling(9).max()
    rsv = ((c - low9) / (high9 - low9).replace(0, np.nan) * 100)
    kdj_k = rsv.ewm(com=2, adjust=False).mean()
    kdj_d = kdj_k.ewm(com=2, adjust=False).mean()
    kdj_j = 3 * kdj_k - 2 * kdj_d
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (typical * df["volume"]).cumsum() / df["volume"].cumsum().replace(0, np.nan)

    def last(s: pd.Series) -> float | None:
        v = s.iloc[-1] if len(s) else None
        return None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)

    price = last(c)
    s50, s200 = last(sma50), last(sma200)
    rsi_last = last(rsi)

    # Trend: price vs long MAs + golden/death cross.
    trend = "neutral"
    if price and s50 and s200:
        if price > s50 > s200:
            trend = "uptrend"
        elif price < s50 < s200:
            trend = "downtrend"

    signals: list[str] = []
    if rsi_last is not None:
        if rsi_last >= 70:
            signals.append(f"RSI {rsi_last:.0f} — overbought")
        elif rsi_last <= 30:
            signals.append(f"RSI {rsi_last:.0f} — oversold")
    if last(macd) is not None and last(macd_signal) is not None:
        signals.append("MACD above signal (bullish)" if last(macd) > last(macd_signal) else "MACD below signal (bearish)")
    if price and s200:
        signals.append("Above 200-day MA" if price > s200 else "Below 200-day MA")

    return TechnicalAnalysis(
        dates=df["date"].tolist(),
        sma20=_clean(sma20), sma50=_clean(sma50), sma200=_clean(sma200),
        ema12=_clean(ema12), ema26=_clean(ema26),
        bb_upper=_clean(bb_upper), bb_lower=_clean(bb_lower),
        rsi14=_clean(rsi), macd=_clean(macd), macd_signal=_clean(macd_signal),
        macd_hist=_clean(macd_hist), atr14=_clean(atr), vwap=_clean(vwap),
        kdj_k=_clean(kdj_k), kdj_d=_clean(kdj_d), kdj_j=_clean(kdj_j),
        latest={
            "price": price, "sma20": last(sma20), "sma50": s50, "sma200": s200,
            "ema12": last(ema12), "ema26": last(ema26), "rsi14": rsi_last,
            "macd": last(macd), "macd_signal": last(macd_signal), "macd_hist": last(macd_hist),
            "atr14": last(atr), "bb_upper": last(bb_upper), "bb_lower": last(bb_lower),
            "kdj_k": last(kdj_k), "kdj_d": last(kdj_d), "kdj_j": last(kdj_j),
        },
        trend=trend,
        signals=signals,
    )
