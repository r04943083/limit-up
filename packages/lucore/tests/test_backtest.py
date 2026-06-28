"""Strategy backtester: deterministic behavior on synthetic price series."""
import datetime as dt

from lucore.compute.backtest import StrategySpec, backtest
from lucore.data.base import Bar


def _bars(closes: list[float]) -> list[Bar]:
    base = dt.date(2020, 1, 1)
    return [
        Bar(date=base + dt.timedelta(days=i), open=c, high=c + 1, low=c - 1, close=c, volume=1000.0)
        for i, c in enumerate(closes)
    ]


def test_ma_cross_buys_uptrend_and_beats_cash():
    # Monotonic uptrend: fast MA stays above slow MA → enter once, ride it up.
    closes = [100 + i for i in range(120)]
    r = backtest("UP", _bars(closes), StrategySpec(kind="ma_cross", fast=5, slow=20))
    assert r.bars == 120
    assert r.stats.total_return_pct > 0
    # Long-only fully invested ≈ buy & hold once entered.
    assert r.stats.exposure_pct > 0.5
    assert len(r.curve) == 120


def test_rsi_round_trips_and_records_closed_trade():
    # Down then up: RSI dips below buy threshold, then recovers above sell → one closed trade.
    closes = [100 - i for i in range(20)] + [80 + i * 2 for i in range(30)]
    r = backtest("V", _bars(closes), StrategySpec(kind="rsi", rsi_period=5, rsi_buy=30, rsi_sell=70))
    assert r.stats.trades >= 1
    assert all(t.return_pct is not None for t in r.trade_log if t.exit_date)


def test_flat_series_no_trades_no_drawdown():
    r = backtest("FLAT", _bars([100.0] * 60), StrategySpec(kind="ma_cross", fast=5, slow=20))
    assert r.stats.trades == 0
    assert r.stats.max_drawdown_pct == 0.0
    assert abs(r.stats.total_return_pct) < 1e-9
