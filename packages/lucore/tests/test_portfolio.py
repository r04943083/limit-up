"""Deterministic portfolio analytics tests (no network)."""
from lucore.compute.portfolio import (
    PositionInput,
    compute_correlation,
    compute_portfolio,
    returns_from_closes,
)


def test_compute_portfolio_values_and_weights():
    positions = [
        PositionInput(symbol="AAA", market="US", quantity=10, avg_cost=100, price=150, currency="USD", sector="Tech"),
        PositionInput(symbol="BBB", market="US", quantity=5, avg_cost=200, price=100, currency="USD", sector="Energy"),
    ]
    a = compute_portfolio(positions, {"USD": 1.0}, "USD")
    # AAA mv = 1500, BBB mv = 500 -> total 2000
    assert a.total_value == 2000
    assert a.total_cost == 1000 + 1000  # 10*100 + 5*200
    assert round(a.positions[0].weight, 3) == 0.75
    assert round(a.positions[0].pnl, 1) == 500.0  # (150-100)*10
    assert round(a.positions[1].pnl, 1) == -500.0  # (100-200)*5
    assert a.total_pnl == 0.0
    assert round(a.top_weight, 2) == 0.75
    assert round(a.hhi, 4) == round(0.75**2 + 0.25**2, 4)
    assert round(a.sector_alloc["Tech"], 2) == 0.75


def test_fx_conversion():
    positions = [
        PositionInput(symbol="0700.HK", market="HK", quantity=100, avg_cost=300, price=400, currency="HKD"),
    ]
    a = compute_portfolio(positions, {"HKD": 0.128, "USD": 1.0}, "USD")
    assert round(a.total_value, 2) == round(100 * 400 * 0.128, 2)
    assert round(a.positions[0].pnl_pct, 1) == round((400 - 300) / 300 * 100, 1)


def test_correlation():
    rets = {"X": returns_from_closes([1, 2, 3, 4, 5]), "Y": returns_from_closes([2, 4, 6, 8, 10])}
    syms, matrix = compute_correlation(rets)
    assert set(syms) == {"X", "Y"}
    # Perfectly proportional series -> correlation ~ 1
    i, j = syms.index("X"), syms.index("Y")
    assert abs(matrix[i][j] - 1.0) < 1e-6
