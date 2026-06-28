"""Unit tests for the akshare CN-market mapping helpers (pure, no network)."""
from lucore.data.cn_market import (
    DragonTiger,
    HsgtSummary,
    LimitUpPool,
    LimitUpStock,
    _f,
    _hhmm,
    _i,
    _s,
)


def test_hhmm_formats_seal_time():
    assert _hhmm("092500") == "09:25"
    assert _hhmm("111109") == "11:11"
    assert _hhmm("150000") == "15:00"
    assert _hhmm(None) is None
    assert _hhmm("") is None


def test_numeric_coercers():
    assert _f("10.5") == 10.5
    assert _f(None) is None
    assert _f("n/a") is None
    assert _i("3.0") == 3
    assert _i(None) is None
    assert _s("  元件 ") == "元件"
    assert _s("") is None


def test_models_default_empty_and_roundtrip():
    pool = LimitUpPool(date="20260628", count=1,
                       stocks=[LimitUpStock(code="000823", name="超声电子", pct=10.0, boards=3)])
    back = LimitUpPool.model_validate_json(pool.model_dump_json())
    assert back.stocks[0].boards == 3
    assert back.count == 1
    assert DragonTiger(date="20260628").rows == []
    assert HsgtSummary().northbound_suspended is True
