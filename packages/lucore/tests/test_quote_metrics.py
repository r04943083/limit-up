"""Pure per-quote metric math for the Futu-style watchlist columns."""
import pytest

from lucore.compute import quote_metrics as qm


def test_shares_outstanding():
    assert qm.shares_outstanding(1_000_000.0, 100.0) == 10_000.0
    assert qm.shares_outstanding(None, 100.0) is None
    assert qm.shares_outstanding(1_000.0, 0.0) is None


def test_turnover_rate():
    # 1000 shares traded out of 10_000 outstanding = 10%
    assert qm.turnover_rate(1_000.0, 10_000.0) == pytest.approx(0.10)
    assert qm.turnover_rate(None, 10_000.0) is None
    assert qm.turnover_rate(1_000.0, 0.0) is None


def test_volume_ratio():
    assert qm.volume_ratio(200.0, [100.0, 100.0, 100.0]) == pytest.approx(2.0)
    assert qm.volume_ratio(200.0, []) is None
    assert qm.volume_ratio(None, [100.0]) is None
    # zero/None prior volumes are ignored
    assert qm.volume_ratio(150.0, [0.0, 100.0, None]) == pytest.approx(1.5)


def test_amplitude():
    assert qm.amplitude(110.0, 90.0, 100.0) == pytest.approx(0.20)
    assert qm.amplitude(None, 90.0, 100.0) is None
    assert qm.amplitude(110.0, 90.0, 0.0) is None


def test_pct_from_high():
    assert qm.pct_from_high(90.0, 100.0) == pytest.approx(-0.10)
    assert qm.pct_from_high(100.0, 100.0) == pytest.approx(0.0)
    assert qm.pct_from_high(None, 100.0) is None
