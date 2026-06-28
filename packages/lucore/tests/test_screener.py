"""Deterministic screener tests (no network)."""
from lucore.compute.screener import ScreenInput, screen


def _mk(**kw) -> ScreenInput:
    return ScreenInput(**kw)


def test_value_screen():
    inputs = [
        _mk(symbol="CHEAP", pe_ttm=12, pb=2),
        _mk(symbol="EXPENSIVE", pe_ttm=60, pb=15),
        _mk(symbol="NOPE", pe_ttm=-5),  # negative earnings -> excluded
    ]
    out = screen("value", inputs)
    syms = [c.symbol for c in out]
    assert "CHEAP" in syms and "EXPENSIVE" not in syms and "NOPE" not in syms


def test_growth_ranks_by_growth():
    inputs = [
        _mk(symbol="FAST", revenue_growth=0.40),
        _mk(symbol="OK", revenue_growth=0.20),
        _mk(symbol="SLOW", revenue_growth=0.05),
    ]
    out = screen("growth", inputs)
    assert [c.symbol for c in out] == ["FAST", "OK"]  # SLOW filtered, ranked desc


def test_momentum_requires_uptrend():
    inputs = [
        _mk(symbol="UP", trend="uptrend", rsi=60, price=110, sma200=100),
        _mk(symbol="DOWN", trend="downtrend", rsi=40, price=90, sma200=100),
    ]
    out = screen("momentum", inputs)
    assert [c.symbol for c in out] == ["UP"]


def test_ai_theme_membership():
    inputs = [_mk(symbol="NVDA"), _mk(symbol="KO")]
    out = screen("ai", inputs)
    assert [c.symbol for c in out] == ["NVDA"]
