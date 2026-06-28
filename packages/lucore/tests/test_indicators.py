"""Deterministic indicator tests on synthetic data (no network)."""
import datetime as dt

from lucore.compute.indicators import compute_technical
from lucore.data.base import Bar


def _bars(closes: list[float]) -> list[Bar]:
    start = dt.date(2024, 1, 1)
    out = []
    for i, c in enumerate(closes):
        out.append(
            Bar(date=start + dt.timedelta(days=i), open=c, high=c + 1, low=c - 1, close=c, volume=1000)
        )
    return out


def test_sma_and_length():
    closes = [float(i) for i in range(1, 61)]  # 1..60 rising
    ta = compute_technical(_bars(closes))
    assert len(ta.dates) == 60
    # SMA20 at the end = mean(41..60) = 50.5
    assert ta.latest["sma20"] is not None
    assert abs(ta.latest["sma20"] - 50.5) < 1e-6


def test_rsi_bounds_and_uptrend():
    closes = [float(i) for i in range(1, 261)]  # strictly rising → strong RSI, uptrend
    ta = compute_technical(_bars(closes))
    rsi = ta.latest["rsi14"]
    assert rsi is not None and 0 <= rsi <= 100
    assert rsi > 70  # monotonic rise → overbought
    assert ta.trend == "uptrend"


def test_downtrend():
    closes = [float(i) for i in range(260, 0, -1)]  # strictly falling
    ta = compute_technical(_bars(closes))
    assert ta.trend == "downtrend"
    assert ta.latest["rsi14"] < 30
