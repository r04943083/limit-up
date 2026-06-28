"""Phase 0 smoke tests: market inference + DB bootstrap."""
from lucore.markets import Market, infer_market


def test_infer_market():
    assert infer_market("NVDA") == Market.US
    assert infer_market("AAPL") == Market.US
    assert infer_market("0700.HK") == Market.HK
    assert infer_market("700.HK") == Market.HK
    assert infer_market("600519.SS") == Market.CN
    assert infer_market("000001.SZ") == Market.CN


def test_init_db(tmp_path, monkeypatch):
    # Point the DB at a temp dir and confirm tables get created.
    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]

    # Reset the cached engine so it picks up the temp DB path.
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None

    from lucore.db import init_db, session_scope
    from lucore.db.models import Stock

    init_db()
    with session_scope() as s:
        s.add(Stock(symbol="NVDA", market="US", name="NVIDIA"))
    with session_scope() as s:
        got = s.get(Stock, "NVDA")
        assert got is not None
        assert got.name == "NVIDIA"
