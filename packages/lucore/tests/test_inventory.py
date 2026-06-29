"""Data inventory: per-market stock / bar / coverage counts over the local DB."""
import datetime as dt

import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None

    from lucore.db import init_db, session_scope
    from lucore.db.models import FinancialsCache, PriceBar, Snapshot, Stock

    init_db()
    with session_scope() as s:  # stocks first (FK target) so bar inserts satisfy the constraint
        s.add_all([
            Stock(symbol="NVDA", market="US", name="NVIDIA"),
            Stock(symbol="AAPL", market="US", name="Apple"),
            Stock(symbol="0700.HK", market="HK", name="Tencent"),
            Stock(symbol="600519.SS", market="CN", name="Kweichow Moutai"),
        ])
    with session_scope() as s:
        # NVDA: 2 bars + snapshot + financials; AAPL: 1 bar only; HK: snapshot only.
        s.add_all([
            PriceBar(symbol="NVDA", interval="1d", date=dt.date(2026, 1, 2), open=1, high=1, low=1, close=1, volume=1),
            PriceBar(symbol="NVDA", interval="1d", date=dt.date(2026, 1, 3), open=1, high=1, low=1, close=1, volume=1),
            PriceBar(symbol="AAPL", interval="1d", date=dt.date(2026, 1, 2), open=1, high=1, low=1, close=1, volume=1),
        ])
        s.add(Snapshot(symbol="NVDA", bundle_json="{}"))
        s.add(Snapshot(symbol="0700.HK", bundle_json="{}"))
        s.add(FinancialsCache(symbol="NVDA", payload_json="{}"))
    import lucore.services.inventory as inv
    return inv


def test_totals(db):
    inv = db.get_inventory()
    assert inv.total_stocks == 4
    assert inv.total_bars == 3
    assert inv.total_snapshots == 2
    assert inv.db_bytes and inv.db_bytes > 0


def test_per_market_counts(db):
    inv = db.get_inventory()
    by = {m.market: m for m in inv.markets}
    assert by["US"].stocks == 2
    assert by["US"].bars == 3
    assert by["US"].with_bars == 2          # NVDA + AAPL
    assert by["US"].with_snapshot == 1      # NVDA only
    assert by["US"].with_financials == 1    # NVDA only
    assert by["HK"].with_snapshot == 1
    assert by["HK"].with_bars == 0
    assert by["CN"].stocks == 1
    assert by["CN"].with_bars == 0


def test_labels_present(db):
    inv = db.get_inventory()
    labels = {m.market: m.label for m in inv.markets}
    assert labels["US"] == "美股"
    assert labels["CN"] == "A股"
    assert labels["HK"] == "港股"
