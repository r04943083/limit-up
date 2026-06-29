"""Index-constituent fetching: symbol normalisation + per-index error isolation."""
import lucore.data.universe as u


def test_cn_symbol_by_exchange():
    assert u._cn_symbol("600519", "上海证券交易所") == "600519.SS"
    assert u._cn_symbol("000001", "深圳证券交易所") == "000001.SZ"


def test_cn_symbol_by_prefix():
    assert u._cn_symbol("688981") == "688981.SS"   # STAR (Shanghai)
    assert u._cn_symbol("600000") == "600000.SS"   # Shanghai main board
    assert u._cn_symbol("300750") == "300750.SZ"   # ChiNext (Shenzhen)
    assert u._cn_symbol("000001") == "000001.SZ"   # Shenzhen main board
    assert u._cn_symbol("abc") is None


def test_constituents_dispatches_by_market(monkeypatch):
    monkeypatch.setattr(u, "_fetch_cn", lambda key: [("600519.SS", "贵州茅台")])
    monkeypatch.setattr(u, "_fetch_us", lambda key: [("NVDA", "NVIDIA")])
    monkeypatch.setattr(u, "_fetch_hk", lambda key: [("0700.HK", "Tencent")])
    assert u.constituents("csi300") == [("600519.SS", "贵州茅台")]
    assert u.constituents("sp500") == [("NVDA", "NVIDIA")]
    assert u.constituents("hsi") == [("0700.HK", "Tencent")]


def test_constituents_unknown_key_is_empty():
    assert u.constituents("nope") == []


def test_constituents_swallows_fetch_errors(monkeypatch):
    def boom(key):
        raise RuntimeError("network down")

    monkeypatch.setattr(u, "_fetch_us", boom)
    assert u.constituents("sp500") == []  # degrades to empty, doesn't raise
