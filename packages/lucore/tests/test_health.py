"""Health score is deterministic compute — pin its behavior."""
from lucore.compute.health import health_score


def test_strong_uptrend_above_200dma():
    h = health_score(
        price=100, sma50=90, sma200=80, rsi=58, trend="uptrend",
        week52_low=60, week52_high=105,
    )
    assert h.score >= 75
    assert h.label in ("strong", "healthy")
    assert "above 200DMA" in h.factors


def test_weak_downtrend_below_200dma():
    h = health_score(
        price=70, sma50=80, sma200=90, rsi=35, trend="downtrend",
        week52_low=65, week52_high=120,
    )
    assert h.score <= 45
    assert h.label in ("weak", "poor", "neutral")
    assert "below 200DMA" in h.factors


def test_overbought_penalized():
    hot = health_score(price=100, sma200=80, rsi=85, trend="uptrend", week52_low=50, week52_high=101)
    calm = health_score(price=100, sma200=80, rsi=58, trend="uptrend", week52_low=50, week52_high=101)
    assert hot.score < calm.score
    assert any("overbought" in f for f in hot.factors)


def test_missing_data_defaults_to_neutral():
    h = health_score()
    assert h.score == 50.0
    assert h.label == "neutral"


def test_new_high_above_cached_52w_range_is_clamped():
    # Today's price prints above the cached 52w high (a fresh high not yet in the range).
    # The 52w-position sub-score must clamp at its cap, not exceed it and inflate the score.
    over = health_score(price=110, sma200=80, rsi=58, trend="uptrend", week52_low=60, week52_high=100)
    at = health_score(price=100, sma200=80, rsi=58, trend="uptrend", week52_low=60, week52_high=100)
    assert over.score == at.score  # clamped: a new-high price can't push it past the cap
