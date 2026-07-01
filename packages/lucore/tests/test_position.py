"""Deterministic position sizing: vote tally + conviction → sized action, risk-capped."""
from lucore.compute.position import MAX_WEIGHT_PCT, suggest_position


def test_strong_bullish_high_conviction_buys():
    r = suggest_position(bullish=8, neutral=1, bearish=1, avg_score=8.0)
    assert r.action == "buy" and r.label.startswith("买入")
    assert 0 < r.target_weight_pct <= MAX_WEIGHT_PCT
    assert r.directional == round((8 - 1) / 10, 2)


def test_mild_bullish_adds_small():
    r = suggest_position(bullish=4, neutral=4, bearish=2, avg_score=5.8)
    assert r.action == "add" and 0 < r.target_weight_pct <= MAX_WEIGHT_PCT


def test_net_bearish_sells_no_long_weight():
    r = suggest_position(bullish=1, neutral=1, bearish=6, avg_score=4.0)
    assert r.action == "sell" and r.target_weight_pct == 0.0


def test_mixed_holds():
    r = suggest_position(bullish=3, neutral=4, bearish=3, avg_score=5.0)
    assert r.action == "hold" and r.target_weight_pct == 0.0


def test_weight_capped_and_scales_with_conviction():
    strong = suggest_position(10, 0, 0, 10.0)   # directional 1.0, conviction 1.0
    assert strong.target_weight_pct == MAX_WEIGHT_PCT
    weaker = suggest_position(10, 0, 0, 7.0)     # lower conviction → smaller size
    assert weaker.target_weight_pct < strong.target_weight_pct


def test_label_is_monotonic_with_weight():
    # A unanimous-but-moderate tally (bigger size) must be labeled 买入, and a split-but-directional
    # tally (smaller size) 小仓参与 — the 买入 weight must not be smaller than the 小仓参与 weight.
    big = suggest_position(10, 0, 0, 6.4)      # directional 1.0, conviction .64 → 6.4%
    small = suggest_position(6, 1, 3, 6.6)      # directional 0.5, conviction .66 → 3.3%
    assert big.action == "buy" and small.action == "add"
    assert big.target_weight_pct >= small.target_weight_pct


def test_empty_tally():
    r = suggest_position(0, 0, 0, 0.0)
    assert r.action == "hold" and r.target_weight_pct == 0.0
