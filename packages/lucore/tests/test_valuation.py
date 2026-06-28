"""DCF valuation: deterministic math checked against hand-computed values."""
import math

from lucore.compute.valuation import dcf, implied_growth_from_fcf


def test_dcf_known_values():
    # fcf_base=100, growth=0, discount=10%, terminal_growth=0, years=3, shares=10, net_debt=0
    # Year FCF = 100 each (growth 0). PVs: 100/1.1, 100/1.1^2, 100/1.1^3
    r = dcf(fcf_base=100.0, growth=0.0, discount=0.10, terminal_growth=0.0, years=3,
            shares=10.0, net_debt=0.0)
    pv1, pv2, pv3 = 100 / 1.1, 100 / 1.1**2, 100 / 1.1**3
    assert math.isclose(r.pv_explicit, pv1 + pv2 + pv3, rel_tol=1e-9)
    # Terminal value (tg=0): TV = fcf_final / discount = 100 / 0.1 = 1000; PV = 1000/1.1^3
    assert math.isclose(r.terminal_value, 1000.0, rel_tol=1e-9)
    assert math.isclose(r.pv_terminal, 1000.0 / 1.1**3, rel_tol=1e-9)
    assert math.isclose(r.enterprise_value, r.pv_explicit + r.pv_terminal, rel_tol=1e-12)
    assert math.isclose(r.equity_value, r.enterprise_value, rel_tol=1e-12)  # net_debt 0
    assert math.isclose(r.intrinsic_per_share, r.equity_value / 10.0, rel_tol=1e-12)
    assert len(r.table) == 3


def test_dcf_net_debt_reduces_equity():
    no_debt = dcf(100, growth=0.05, discount=0.1, years=5, shares=10, net_debt=0)
    with_debt = dcf(100, growth=0.05, discount=0.1, years=5, shares=10, net_debt=200)
    assert with_debt.equity_value == no_debt.equity_value - 200
    assert with_debt.intrinsic_per_share < no_debt.intrinsic_per_share


def test_dcf_clamps_terminal_above_discount():
    # terminal_growth >= discount would blow up; it must be clamped below discount.
    r = dcf(100, growth=0.0, discount=0.08, terminal_growth=0.12, years=3, shares=10)
    assert r.terminal_growth < r.discount
    assert r.intrinsic_per_share is not None and r.intrinsic_per_share > 0


def test_dcf_no_shares_yields_no_per_share():
    r = dcf(100, growth=0.05, discount=0.1, years=5, shares=None)
    assert r.intrinsic_per_share is None


def test_implied_growth_cagr_and_clamp():
    # newest-first: 121, 110, 100 -> CAGR oldest(100)->newest(121) over 2 yrs = 10%
    g = implied_growth_from_fcf([121.0, 110.0, 100.0])
    assert math.isclose(g, 0.10, rel_tol=1e-6)
    # explosive growth is clamped to 25%
    assert implied_growth_from_fcf([1000.0, 10.0]) == 0.25
    # insufficient / non-positive data -> None
    assert implied_growth_from_fcf([100.0]) is None
    assert implied_growth_from_fcf([100.0, -5.0]) is None
