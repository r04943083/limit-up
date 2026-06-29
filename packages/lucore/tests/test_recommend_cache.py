"""Recommend screening is cache-first: it reads snapshots, never the network."""
import json

import pytest


def _bundle(symbol, **f):
    fundamentals = {"symbol": symbol, "name": symbol, "sector": "Technology",
                    "market": "US", "currency": "USD", **f}
    return json.dumps({
        "symbol": symbol, "market": "US",
        "quote": {"symbol": symbol, "market": "US", "price": 100.0, "currency": "USD", "name": symbol},
        "fundamentals": fundamentals,
        "technical_latest": {"price": 100.0, "rsi14": 55.0, "sma50": 95.0, "sma200": 90.0},
        "technical_trend": "uptrend", "technical_signals": [], "news": [], "spark": [],
        "generated_at": "2026-06-29T00:00:00+00:00",
    })


@pytest.fixture()
def env(tmp_path, monkeypatch):
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
            Snapshot(symbol="FAST", bundle_json=_bundle("FAST", revenue_growth=0.40, pe_ttm=30, pb=8, market_cap=3e11)),
            Snapshot(symbol="CHEAP", bundle_json=_bundle("CHEAP", revenue_growth=0.05, pe_ttm=10, pb=1.2, market_cap=2e11)),
            # Delisted junk: collapsed price → tiny P/E but must be filtered (micro-cap + freefall).
            Snapshot(symbol="DEAD", bundle_json=_bundle("DEAD", revenue_growth=0.0, pe_ttm=2, pb=0.1, market_cap=1e7)),
        ])
    import lucore.services.recommend as rec
    # Any accidental network call would go through the data router → make it explode so the
    # test fails loudly if the cache-first path regresses.
    import lucore.data.router as router_mod
    monkeypatch.setattr(router_mod, "get_router", lambda: (_ for _ in ()).throw(AssertionError("network!")))
    return rec


def test_cached_universe_lists_snapshots(env):
    assert set(env._cached_universe()) == {"FAST", "CHEAP", "DEAD"}


def test_screen_growth_uses_cache(env):
    cands = env.screen_category("growth", top_n=5)
    assert [c.symbol for c in cands] == ["FAST"]  # only FAST clears the 15% growth bar


def test_screen_value_excludes_delisted_junk(env):
    # DEAD has the lowest P/E but is a micro-cap → must be filtered before scoring.
    cands = env.screen_category("value", top_n=5)
    assert [c.symbol for c in cands] == ["CHEAP"]  # pe<=22 & pb<=4, and investable


def test_facts_for_reads_snapshot(env):
    cands = env.screen_category("growth", top_n=5)
    facts = env._facts_for(cands)
    assert facts and facts[0]["symbol"] == "FAST"
    assert facts[0]["revenue_growth"] == 0.40


def test_investable_floor_filters_microcap_and_freefall(env):
    si = env.ScreenInput
    assert env._is_investable(si(symbol="OK", market_cap=2e11, price=100, sma200=90))
    assert not env._is_investable(si(symbol="SMALL", market_cap=1e8, price=100, sma200=90))
    assert not env._is_investable(si(symbol="CRASH", market_cap=2e11, price=20, sma200=90))
    assert not env._is_investable(si(symbol="NOCAP", market_cap=None, price=100, sma200=90))
