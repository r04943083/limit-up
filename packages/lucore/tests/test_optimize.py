"""Portfolio optimization (mean-variance / risk-parity / Black-Litterman) + integer allocation."""
import numpy as np

from lucore.compute.optimize import (
    black_litterman, discrete_allocation, optimize,
)


def _synthetic_returns(seed=0, t=300):
    rng = np.random.default_rng(seed)
    # A: low vol, B: high vol, C: medium — independent.
    a = rng.normal(0.0005, 0.005, t)
    b = rng.normal(0.0008, 0.030, t)
    c = rng.normal(0.0006, 0.015, t)
    return np.column_stack([a, b, c])


def test_weights_sum_to_one_and_nonnegative():
    r = _synthetic_returns()
    for method in ("max_sharpe", "min_variance", "risk_parity"):
        w = optimize(["A", "B", "C"], r, method=method)
        assert abs(sum(w.weights) - 1.0) < 1e-3
        assert all(x >= 0 for x in w.weights)
        assert w.method == method


def test_min_variance_favors_low_vol_asset():
    r = _synthetic_returns()
    w = optimize(["A", "B", "C"], r, method="min_variance")
    wd = dict(zip(["A", "B", "C"], w.weights))
    assert wd["A"] > wd["B"]  # low-vol A gets more weight than high-vol B


def test_risk_parity_is_inverse_vol_ordered():
    r = _synthetic_returns()
    w = optimize(["A", "B", "C"], r, method="risk_parity")
    wd = dict(zip(["A", "B", "C"], w.weights))
    assert wd["A"] > wd["C"] > wd["B"]  # inverse-vol: A(low) > C(mid) > B(high)


def test_degenerate_inputs_equal_weight():
    w = optimize(["A", "B"], np.zeros((1, 2)), method="max_sharpe")  # <2 rows
    assert w.weights == [0.5, 0.5]
    assert optimize([], np.zeros((0, 0))).weights == []


def test_black_litterman_view_tilts_weight():
    r = _synthetic_returns()
    mkt = [1 / 3, 1 / 3, 1 / 3]
    base = black_litterman(["A", "B", "C"], r, mkt, views={})
    bullA = black_litterman(["A", "B", "C"], r, mkt, views={"A": 40.0})  # strong +40% view on A
    ai = base.weights[0]
    bi = bullA.weights[0]
    assert bi > ai  # a bullish view on A raises A's posterior weight
    assert abs(sum(bullA.weights) - 1.0) < 1e-3


def test_max_sharpe_degeneration_falls_back_to_min_variance():
    rng = np.random.default_rng(7)
    # All assets drift DOWN → long-only tangency portfolio is empty → fall back to min-variance.
    r = np.column_stack([rng.normal(-0.001, 0.006, 300), rng.normal(-0.0015, 0.02, 300)])
    w = optimize(["A", "B"], r, method="max_sharpe")
    assert w.note is not None and "最小方差" in w.note
    assert abs(sum(w.weights) - 1.0) < 1e-3 and all(x >= 0 for x in w.weights)


def test_black_litterman_zero_variance_asset_does_not_crash():
    rng = np.random.default_rng(3)
    a = rng.normal(0.0005, 0.01, 200)
    b = rng.normal(0.0006, 0.02, 200)
    c = np.zeros(200)  # constant price → zero variance (omega floor must keep the view usable)
    r = np.column_stack([a, b, c])
    w = black_litterman(["A", "B", "C"], r, [1 / 3, 1 / 3, 1 / 3], views={"C": 30.0})
    assert abs(sum(w.weights) - 1.0) < 1e-3 and all(x >= 0 for x in w.weights)


def test_discrete_allocation_respects_capital():
    plan = discrete_allocation(["A", "B", "C"], [0.5, 0.3, 0.2], [100.0, 50.0, 200.0], 10_000.0)
    spent = sum(a.value for a in plan.allocations)
    assert spent <= 10_000.0 + 1e-6
    assert plan.leftover_cash >= 0
    assert abs(spent + plan.leftover_cash - 10_000.0) < 1e-6
    by = {a.symbol: a for a in plan.allocations}
    assert by["A"].shares == 50 and by["B"].shares == 60 and by["C"].shares == 10


def test_discrete_allocation_greedy_topup_uses_leftover():
    # Weights leave cash on the table after flooring; greedy top-up should spend most of it.
    plan = discrete_allocation(["X"], [1.0], [30.0], 100.0)  # floor(100/30)=3 → 90, +1 → 120>100 stop
    assert plan.allocations[0].shares == 3 and plan.leftover_cash == 10.0
