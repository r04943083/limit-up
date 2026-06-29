"""Screener service: deterministic custom filter/sort over cached snapshot fundamentals."""
import json

import pytest


def _bundle(symbol, market, sector, **f):
    quote = {
        "price": f.pop("price", 100.0),
        "change_pct": f.pop("change_pct", 1.0),
        "name": f.pop("name", symbol),
    }
    fundamentals = {"symbol": symbol, "market": market, "sector": sector,
                    "industry": f.pop("industry", "Widgets"), "name": quote["name"], **f}
    return json.dumps({"symbol": symbol, "market": market, "quote": quote, "fundamentals": fundamentals})


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None

    from lucore.db import init_db, session_scope
    from lucore.db.models import Snapshot

    init_db()
    with session_scope() as s:
        s.add_all([
            Snapshot(symbol="VAL", bundle_json=_bundle(
                "VAL", "US", "Financials", pe_ttm=8.0, pb=0.9, ps=1.2, roe=0.22,
                revenue_growth=0.05, market_cap=2e11, dividend_yield=3.5)),
            Snapshot(symbol="GRW", bundle_json=_bundle(
                "GRW", "US", "Technology", pe_ttm=80.0, pb=20.0, ps=18.0, roe=0.40,
                revenue_growth=0.85, market_cap=5e11, dividend_yield=0.0)),
            Snapshot(symbol="0700.HK", bundle_json=_bundle(
                "0700.HK", "HK", "Technology", pe_ttm=18.0, pb=4.0, ps=6.0, roe=0.18,
                revenue_growth=0.12, market_cap=3e12)),
            Snapshot(symbol="600519.SS", bundle_json=_bundle(
                "600519.SS", "CN", "Consumer", pe_ttm=22.0, pb=8.0, ps=12.0, roe=0.30,
                revenue_growth=0.16, market_cap=2e12)),
            Snapshot(symbol="JUNK", bundle_json="{not valid json"),
        ])
    # No A-share limit-up pool in tests — stub it to empty so we don't hit the network.
    import lucore.services.screener as sc
    monkeypatch.setattr(sc, "_limit_up_boards", lambda: {})
    return sc


def test_universe_and_skips_bad_json(db):
    res = db.run_screen(db.ScreenSpec())
    assert res.universe == 4
    assert res.matched == 4


def test_pe_max_filter(db):
    res = db.run_screen(db.ScreenSpec(filters=[db.Filter(field="pe_ttm", max=20.0)]))
    assert {h.symbol for h in res.results} == {"VAL", "0700.HK"}


def test_roe_min_is_percent(db):
    res = db.run_screen(db.ScreenSpec(filters=[db.Filter(field="roe", min=25.0)]))
    assert {h.symbol for h in res.results} == {"GRW", "600519.SS"}


def test_market_filter(db):
    res = db.run_screen(db.ScreenSpec(markets=["US"]))
    assert {h.symbol for h in res.results} == {"VAL", "GRW"}


def test_combined_value_screen(db):
    res = db.run_screen(db.ScreenSpec(filters=[
        db.Filter(field="pe_ttm", max=25.0),
        db.Filter(field="roe", min=20.0),
    ]))
    assert {h.symbol for h in res.results} == {"VAL", "600519.SS"}


def test_sort_desc_and_limit(db):
    res = db.run_screen(db.ScreenSpec(sort_field="market_cap", sort_desc=True, limit=2))
    assert [h.symbol for h in res.results] == ["0700.HK", "600519.SS"]


def test_market_cap_in_yi(db):
    res = db.run_screen(db.ScreenSpec(markets=["US"], sort_field="market_cap", sort_desc=True))
    top = res.results[0]
    assert top.symbol == "GRW"
    assert abs(top.metrics["market_cap"] - 5000.0) < 1e-6


def test_sectors_facet(db):
    res = db.run_screen(db.ScreenSpec())
    assert set(res.sectors) == {"Financials", "Technology", "Consumer"}
