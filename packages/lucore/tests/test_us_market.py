"""US market-breadth feeds: yfinance-quote normalization (derived vol_ratio / from_high_pct)
and cache-first service behavior (serve cache, degrade to ok=False on cold failure)."""
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


def test_row_normalization_and_derived_signals():
    from lucore.data.us_market import _row

    q = {
        "symbol": "abvx", "shortName": "Abivax", "regularMarketPrice": 40.0,
        "regularMarketChange": 11.0, "regularMarketChangePercent": 38.6,
        "regularMarketVolume": 3_000_000, "averageDailyVolume3Month": 1_000_000,
        "marketCap": 2.0e9, "trailingPE": None,
        "fiftyTwoWeekHigh": 50.0, "fiftyTwoWeekLow": 5.0,
    }
    r = _row(q)
    assert r.symbol == "ABVX"  # upper-cased
    assert r.name == "Abivax"
    assert r.change_pct == 38.6
    assert r.vol_ratio == 3.0            # 3M / 1M
    assert r.from_high_pct == -20.0      # (40-50)/50*100
    assert r.pe is None                  # NaN/None safe


def test_row_skips_symbolless_and_nan():
    from lucore.data.us_market import _row

    assert _row({"shortName": "no symbol"}) is None
    r = _row({"symbol": "X", "regularMarketPrice": float("nan")})
    assert r.symbol == "X" and r.price is None  # NaN dropped


def test_fetch_movers_unknown_kind_raises():
    from lucore.data.us_market import fetch_movers

    with pytest.raises(ValueError):
        fetch_movers("not_a_feed")


def test_service_cache_first(db, monkeypatch):
    """First call fetches + caches; second call is served from cache without re-fetching."""
    from lucore.data import us_market as us
    from lucore.services import us_market as svc

    calls = {"n": 0}

    def fake_fetch(kind, count=30):
        calls["n"] += 1
        return us.MoversBoard(kind=kind, label="涨幅榜", count=1,
                              stocks=[us.MoverStock(symbol="NVDA", change_pct=5.0)])

    monkeypatch.setattr(us, "fetch_movers", fake_fetch)

    r1 = svc.get_movers("day_gainers")
    assert r1.ok and r1.board.stocks[0].symbol == "NVDA"
    r2 = svc.get_movers("day_gainers")
    assert r2.ok and r2.board.stocks[0].symbol == "NVDA"
    assert calls["n"] == 1  # second call hit the cache


def test_service_cold_failure_degrades(db, monkeypatch):
    from lucore.data import us_market as us
    from lucore.services import us_market as svc

    def boom(kind, count=30):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(us, "fetch_movers", boom)
    r = svc.get_movers("day_losers")
    assert r.ok is False
    assert "yahoo down" in r.error
    assert r.board.kind == "day_losers" and r.board.count == 0
    assert r.board.label == "跌幅榜"  # label still resolved from the registry


def test_service_serves_stale_cache_on_failure(db, monkeypatch):
    from lucore.data import us_market as us
    from lucore.services import us_market as svc

    good = us.MoversBoard(kind="most_actives", label="成交活跃", count=1,
                          stocks=[us.MoverStock(symbol="AAL", change_pct=0.8)])
    monkeypatch.setattr(us, "fetch_movers", lambda k, count=30: good)
    assert svc.get_movers("most_actives").ok

    # Force a re-fetch by expiring the TTL, then make the source fail — cache is served.
    monkeypatch.setattr(svc.mc, "fresh_enough", lambda *a, **k: False)
    monkeypatch.setattr(us, "fetch_movers", lambda k, count=30: (_ for _ in ()).throw(RuntimeError("down")))
    r = svc.get_movers("most_actives")
    assert r.ok is False and r.board.stocks[0].symbol == "AAL"  # stale-but-present
    assert "down" in r.error


def test_allow_fetch_false_is_cache_only(db, monkeypatch):
    """allow_fetch=False never hits the network: returns cache if any, else empty ok=False."""
    from lucore.data import us_market as us
    from lucore.services import us_market as svc

    calls = {"n": 0}

    def counting_fetch(kind, count=30):
        calls["n"] += 1
        return us.MoversBoard(kind=kind, label="涨幅榜", count=1,
                              stocks=[us.MoverStock(symbol="NVDA")])

    monkeypatch.setattr(us, "fetch_movers", counting_fetch)

    # Cold cache + no fetch → empty, ok=False, and fetch_movers NOT called.
    r0 = svc.get_movers("day_gainers", allow_fetch=False)
    assert r0.ok is False and r0.board.count == 0 and calls["n"] == 0

    # Warm the cache with a real fetch, then a cache-only read serves it without fetching.
    svc.get_movers("day_gainers")
    assert calls["n"] == 1
    r1 = svc.get_movers("day_gainers", allow_fetch=False)
    assert r1.ok and r1.board.stocks[0].symbol == "NVDA" and calls["n"] == 1


def test_list_feeds():
    from lucore.services.us_market import list_feeds

    feeds = list_feeds()
    kinds = [f.kind for f in feeds]
    assert "day_gainers" in kinds and "day_losers" in kinds and "most_actives" in kinds
