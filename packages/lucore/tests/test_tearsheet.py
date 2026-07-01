"""Deterministic tear-sheet math: returns, drawdown, Sharpe/Sortino/Calmar sign, VaR/CVaR,
win-rate, monthly grouping, and benchmark beta/alpha."""
import datetime as dt

from lucore.compute.tearsheet import tearsheet


def _dates(n, start=dt.date(2025, 1, 1)):
    return [start + dt.timedelta(days=i) for i in range(n)]


def test_empty_and_degenerate():
    assert tearsheet([], [], 100.0).n_days == 0
    assert tearsheet(_dates(1), [100.0], 0.0).total_return_pct is None


def test_basic_metrics_monotonic_up():
    eq = [100.0, 101.0, 102.0, 103.0, 104.0]
    ts = tearsheet(_dates(5), eq, 100.0)
    assert ts.total_return_pct == 4.0
    assert ts.max_drawdown_pct == 0.0          # never dropped
    assert ts.win_rate_pct == 100.0            # every day up
    assert ts.worst_day_pct is not None and ts.best_day_pct is not None
    assert ts.sharpe is not None and ts.sharpe > 0
    assert ts.avg_loss_pct is None             # no losing days
    assert ts.profit_factor is None            # no losses → undefined


def test_drawdown_and_var():
    # Up to 120 then crash to 80 then partial recover.
    eq = [100, 110, 120, 100, 80, 90.0]
    ts = tearsheet(_dates(6), eq, 100.0)
    # Peak 120 → trough 80 = 33.33% drawdown.
    assert abs(ts.max_drawdown_pct - 33.33) < 0.1
    assert ts.worst_day_pct is not None and ts.worst_day_pct < 0
    assert ts.var95_pct is not None and ts.var95_pct > 0   # positive loss magnitude
    assert ts.cvar95_pct is not None and ts.cvar95_pct >= ts.var95_pct - 1e-6


def test_monthly_returns_grouping():
    # Two months: Jan ends at 110 (from 100 start), Feb ends at 121.
    dates = [dt.date(2025, 1, 1), dt.date(2025, 1, 15), dt.date(2025, 1, 31),
             dt.date(2025, 2, 10), dt.date(2025, 2, 28)]
    eq = [100.0, 105.0, 110.0, 115.0, 121.0]
    ts = tearsheet(dates, eq, 100.0)
    months = {m.month: m.return_pct for m in ts.monthly_returns}
    # First month has no prior month-end → only Feb produces a return: 121/110 - 1 = 10%.
    assert "2025-02" in months
    assert abs(months["2025-02"] - 10.0) < 0.01


def test_sortino_downside_deviation_uses_total_n():
    import math

    # rets ≈ [+0.02, -0.01, +0.02, -0.01]; downside dev = sqrt((0.01²+0.01²)/N=4).
    eq = [100.0]
    for r in (0.02, -0.01, 0.02, -0.01):
        eq.append(eq[-1] * (1 + r))
    ts = tearsheet(_dates(len(eq)), eq, 100.0)
    mean_r = (0.02 - 0.01 + 0.02 - 0.01) / 4
    dstd = math.sqrt((0.01 ** 2 + 0.01 ** 2) / 4)  # divide by 4 (total), not 2 (down days)
    expected = mean_r / dstd * math.sqrt(252)
    assert ts.sortino is not None and abs(ts.sortino - expected) < 0.1


def test_benchmark_beta_alpha():
    # Portfolio moves exactly 2x the benchmark each day → beta ≈ 2.
    b = [100.0]
    p = [100.0]
    for r in (0.01, -0.02, 0.015, -0.005, 0.02):
        b.append(b[-1] * (1 + r))
        p.append(p[-1] * (1 + 2 * r))
    ts = tearsheet(_dates(len(p)), p, 100.0, benchmark=b)
    assert ts.beta is not None and abs(ts.beta - 2.0) < 0.05
    assert ts.benchmark_return_pct is not None
    assert ts.alpha_pct is not None
