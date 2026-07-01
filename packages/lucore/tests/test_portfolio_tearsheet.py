"""Portfolio tear-sheet: reconstruct a dated equity curve from holdings × cached closes,
align by date, and run the deterministic tear-sheet. Price history is faked."""
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
    from lucore.db import init_db

    init_db()
    yield


def _series(start_price, days=90, drift=0.001):
    d0 = dt.date(2025, 1, 1)
    out = {}
    p = start_price
    for i in range(days):
        p *= (1 + drift)
        out[d0 + dt.timedelta(days=i)] = round(p, 4)
    return out


def test_portfolio_tearsheet_reconstruction(db, monkeypatch):
    from lucore.services import portfolio as pf
    from lucore.services import portfolio_perf as pp

    pid = pf.ensure_default_portfolio()
    pf.upsert_holding(pid, "AAA", 10, 100.0, source="manual")
    pf.upsert_holding(pid, "BBB", 5, 50.0, source="manual")

    aaa = _series(100.0)
    bbb = _series(50.0, drift=0.002)

    def fake_closes(symbol, period="1y", *, refresh=False):
        if symbol == "AAA":
            return aaa
        if symbol == "BBB":
            return bbb
        return {}  # SPY not cached → benchmark omitted

    monkeypatch.setattr(pp, "_dated_closes", fake_closes)
    # FX is US-only here; avoid any network in fx_map by forcing identity.
    monkeypatch.setattr(pp, "fx_map", lambda currencies, base="USD": {c: 1.0 for c in currencies})

    res = pp.compute_portfolio_tearsheet(pid)
    assert res.ok
    assert res.start == "2025-01-01"
    assert res.tearsheet.n_days == 90
    assert res.tearsheet.total_return_pct is not None and res.tearsheet.total_return_pct > 0
    assert res.tearsheet.sharpe is not None
    assert res.tearsheet.benchmark_return_pct is None  # SPY absent


def test_empty_portfolio_degrades(db, monkeypatch):
    from lucore.services import portfolio as pf
    from lucore.services import portfolio_perf as pp

    pid = pf.ensure_default_portfolio()
    res = pp.compute_portfolio_tearsheet(pid)
    assert res.ok is False and "empty" in res.error


def test_no_cached_history_degrades(db, monkeypatch):
    from lucore.services import portfolio as pf
    from lucore.services import portfolio_perf as pp

    pid = pf.ensure_default_portfolio()
    pf.upsert_holding(pid, "AAA", 10, 100.0, source="manual")
    monkeypatch.setattr(pp, "_dated_closes", lambda *a, **k: {})
    res = pp.compute_portfolio_tearsheet(pid)
    assert res.ok is False and "no cached" in res.error
