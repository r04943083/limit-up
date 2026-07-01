"""Portfolio CSV import: multiple lots of the same symbol must AGGREGATE (sum shares,
share-weighted average cost), not overwrite each other, and `added` counts distinct symbols."""
import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None
    from lucore.db import init_db

    init_db()
    yield


def test_multi_lot_same_symbol_aggregates(db):
    from lucore.services import portfolio as pf

    pid = pf.ensure_default_portfolio()
    csv = "symbol,quantity,avg_cost\nAAPL,100,150\nAAPL,50,180\nNVDA,10,900\n"
    added = pf.import_csv(pid, csv)

    assert added == 2  # two DISTINCT symbols, not three rows
    holds = {h.symbol: h for h in pf.list_holdings(pid)}
    assert set(holds) == {"AAPL", "NVDA"}
    # AAPL: 100 + 50 = 150 shares; weighted cost = (100*150 + 50*180) / 150 = 160
    assert holds["AAPL"].quantity == 150
    assert holds["AAPL"].avg_cost == pytest.approx(160.0)
    assert holds["NVDA"].quantity == 10 and holds["NVDA"].avg_cost == pytest.approx(900.0)


def test_import_returns_zero_without_symbol_column(db):
    from lucore.services import portfolio as pf

    pid = pf.ensure_default_portfolio()
    assert pf.import_csv(pid, "foo,bar\n1,2\n") == 0
    assert pf.list_holdings(pid) == []
