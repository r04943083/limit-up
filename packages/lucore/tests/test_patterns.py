"""Deterministic candlestick + chart pattern detection."""
import datetime as dt

from lucore.compute.patterns import detect_patterns
from lucore.data.base import Bar


def _bar(i, o, h, low, c):
    return Bar(date=dt.date(2025, 1, 1) + dt.timedelta(days=i), open=o, high=h, low=low, close=c)


def _flat(n, price=100.0):
    """n small-body bars so the pattern-under-test is the only signal in the window."""
    return [_bar(i, price, price + 0.2, price - 0.2, price + 0.05) for i in range(n)]


def _names(hits):
    return {h.name for h in hits}


def test_doji():
    bars = _flat(5) + [_bar(5, 100.0, 102.0, 98.0, 100.05)]
    assert "十字星" in _names(detect_patterns(bars))


def test_hammer():
    bars = _flat(5) + [_bar(5, 100.0, 101.2, 95.0, 101.0)]  # long lower shadow
    hits = detect_patterns(bars)
    hammer = next(h for h in hits if h.name == "锤子线")
    assert hammer.kind == "bullish"


def test_bullish_engulfing():
    bars = _flat(4) + [_bar(4, 105.0, 105.5, 99.5, 100.0),   # bearish
                       _bar(5, 99.0, 106.5, 98.5, 106.0)]    # bullish engulfs
    hits = detect_patterns(bars)
    eng = next(h for h in hits if h.name == "看涨吞没")
    assert eng.kind == "bullish"


def test_three_black_crows():
    bars = _flat(3) + [
        _bar(3, 110, 110.2, 106, 106.5),
        _bar(4, 106, 106.2, 102, 102.5),
        _bar(5, 102, 102.2, 98, 98.5),
    ]
    hits = detect_patterns(bars)
    crows = next(h for h in hits if h.name == "三只乌鸦")
    assert crows.kind == "bearish"


def test_double_bottom():
    # 25 bars: two similar lows (~80) separated by a bounce, recent.
    bars = []
    # Two ~80 troughs (idx 4 and 11), then a monotonic-up tail so no third swing low forms.
    prices = [100, 95, 90, 85, 80, 85, 90, 92, 90, 86, 82, 80.5, 84, 88, 92, 95, 98,
              100, 102, 104, 106, 108, 110, 112, 114]
    for i, p in enumerate(prices):
        bars.append(_bar(i, p, p + 1.5, p - 1.5, p))
    hits = detect_patterns(bars)
    # The two ~80 troughs should register a double bottom (bullish).
    dbl = [h for h in hits if h.name == "双底(W底)"]
    assert dbl and dbl[0].kind == "bullish"


def test_empty_and_short():
    assert detect_patterns([]) == []
    assert detect_patterns([_bar(0, 100, 101, 99, 100)]) == []
