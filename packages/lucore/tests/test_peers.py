"""Industry-average valuation: median PE/PB/PS over same-industry cached snapshots."""
import json

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
    from lucore.db.models import Snapshot, Stock

    init_db()

    def _snap(symbol, pe, pb, ps):
        bundle = {"fundamentals": {"pe_ttm": pe, "pb": pb, "ps": ps}}
        return Snapshot(symbol=symbol, bundle_json=json.dumps(bundle))

    with session_scope() as s:  # stocks first (FK target)
        s.add_all([
            Stock(symbol="AAA", market="US", name="A", industry="Semiconductors"),
            Stock(symbol="BBB", market="US", name="B", industry="Semiconductors"),
            Stock(symbol="CCC", market="US", name="C", industry="Semiconductors"),
            Stock(symbol="DDD", market="US", name="D", industry="Software"),  # lone peer
        ])
    with session_scope() as s:
        s.add_all([
            _snap("AAA", 10.0, 2.0, 3.0),
            _snap("BBB", 20.0, 4.0, 5.0),
            _snap("CCC", 30.0, 6.0, 7.0),
            _snap("DDD", 99.0, 9.0, 9.0),
        ])
    import lucore.services.peers as peers
    return peers


def test_industry_median_with_enough_peers(db):
    m = db.industry_medians()["Semiconductors"]
    assert m.n == 3
    assert m.pe == 20.0   # median(10,20,30)
    assert m.pb == 4.0
    assert m.ps == 5.0


def test_too_few_peers_returns_none(db):
    # Only one Software peer → below the 3-peer threshold → no misleading average.
    m = db.industry_medians()["Software"]
    assert m.pe is None and m.n == 1


def test_industry_average_for_symbol(db):
    avg = db.industry_average("BBB")
    assert avg is not None and avg.industry == "Semiconductors" and avg.pe == 20.0
    # Unknown symbol → None (no industry).
    assert db.industry_average("ZZZ") is None


def test_cache_roundtrip(db):
    first = db.industry_medians()
    cached = db.industry_medians()  # second call hits the MarketDataCache path
    assert cached["Semiconductors"].pe == first["Semiconductors"].pe == 20.0
