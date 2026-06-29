"""Universe seeding: upsert Stock rows from (mocked) index constituents, dedup + name-fill."""
import pytest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None

    from lucore.db import init_db

    init_db()
    import lucore.services.universe_seed as us
    return us


def test_seed_inserts_rows(env, monkeypatch):
    fake = {
        "csi300": [("600519.SS", "贵州茅台"), ("000001.SZ", "平安银行")],
        "sp500": [("NVDA", "NVIDIA"), ("AAPL", "Apple")],
    }
    monkeypatch.setattr(env, "constituents", lambda key: fake.get(key, []))
    res = env.seed_indices(["csi300", "sp500"])
    assert res.added == 4
    assert res.universe_size == 4
    assert res.total_fetched == 4
    by = {i.key: i for i in res.indices}
    assert by["csi300"].fetched == 2 and by["csi300"].market == "CN"
    assert by["sp500"].market == "US"


def test_seed_dedups_overlap(env, monkeypatch):
    fake = {
        "csi300": [("600519.SS", "贵州茅台"), ("000001.SZ", "平安银行")],
        "sse50": [("600519.SS", "贵州茅台")],  # overlaps csi300
    }
    monkeypatch.setattr(env, "constituents", lambda key: fake.get(key, []))
    res = env.seed_indices(["csi300", "sse50"])
    assert res.added == 2          # 600519 counted once
    assert res.universe_size == 2
    assert res.total_fetched == 3  # raw fetched still 2+1


def test_seed_fills_missing_name(env, monkeypatch):
    from lucore.db import session_scope
    from lucore.db.models import Stock

    with session_scope() as s:
        s.add(Stock(symbol="0700.HK", market="HK", name=None))
    monkeypatch.setattr(env, "constituents", lambda key: [("0700.HK", "Tencent")])
    res = env.seed_indices(["hsi"])
    assert res.added == 0  # already existed
    with session_scope() as s:
        assert s.get(Stock, "0700.HK").name == "Tencent"


def test_symbols_missing_snapshot(env, monkeypatch):
    from lucore.db import session_scope
    from lucore.db.models import Snapshot, Stock

    with session_scope() as s:
        s.add_all([Stock(symbol="NVDA", market="US", name="NVIDIA"),
                   Stock(symbol="AAPL", market="US", name="Apple")])
    with session_scope() as s:
        s.add(Snapshot(symbol="NVDA", bundle_json="{}"))
    assert env.symbols_missing_snapshot() == ["AAPL"]
