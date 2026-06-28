"""Watchlist JSON backup: export -> import round-trip + merge dedupe (no network).

`add_item` calls ensure_stock which would normally hit the network; we monkeypatch it
to a no-op stand-in that just satisfies the FK, so these stay pure DB tests.
"""
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
    from lucore.db.models import Stock

    init_db()

    def _ensure(symbol, name=None, **fields):  # noqa: ANN001
        with session_scope() as s:
            if s.get(Stock, symbol) is None:
                s.add(Stock(symbol=symbol, market="US", name=name or symbol))

    import lucore.services.watchlist as wl

    monkeypatch.setattr(wl, "ensure_stock", _ensure)
    return wl


def _seed(db):
    g1 = db.create_watchlist("Core")
    db.add_item(g1.id, "NVDA", tags="ai,chip")
    db.add_item(g1.id, "AAPL")
    g2 = db.create_watchlist("HK")
    db.add_item(g2.id, "0700.HK", note="Tencent")
    return g1, g2


def test_export_shape(db):
    _seed(db)
    payload = db.export_all_json()
    assert payload["version"] == 1
    assert "exported_at" in payload
    names = [g["name"] for g in payload["watchlists"]]
    assert names == ["Core", "HK"]
    core = payload["watchlists"][0]
    assert [it["symbol"] for it in core["items"]] == ["NVDA", "AAPL"]
    assert core["items"][0]["tags"] == "ai,chip"


def test_replace_round_trip(db):
    _seed(db)
    backup = db.export_all_json()

    # Mutate the live DB, then restore from backup with replace -> back to original.
    db.create_watchlist("Junk")
    res = db.import_json(backup, mode="replace")
    assert res.mode == "replace"
    assert res.total_added == 3

    after = db.export_all_json()
    assert [g["name"] for g in after["watchlists"]] == ["Core", "HK"]
    assert [it["symbol"] for it in after["watchlists"][0]["items"]] == ["NVDA", "AAPL"]
    # tags + notes preserved through the round-trip
    assert after["watchlists"][0]["items"][0]["tags"] == "ai,chip"
    assert after["watchlists"][1]["items"][0]["note"] == "Tencent"


def test_merge_dedupes(db):
    g1, _ = _seed(db)
    backup = db.export_all_json()

    # Merge the same backup back in: nothing new should be added (all present).
    res = db.import_json(backup, mode="merge")
    assert res.mode == "merge"
    assert res.total_added == 0
    # Core still has exactly NVDA + AAPL, no duplicates.
    assert [i.symbol for i in db.get_watchlist(g1.id).items] == ["NVDA", "AAPL"]


def test_merge_adds_new_only(db):
    g1, _ = _seed(db)
    # A backup that adds MSFT to Core and a brand-new group.
    payload = {
        "version": 1,
        "watchlists": [
            {"name": "Core", "items": [{"symbol": "NVDA"}, {"symbol": "MSFT"}]},
            {"name": "New", "items": [{"symbol": "TSLA"}]},
        ],
    }
    res = db.import_json(payload, mode="merge")
    assert res.total_added == 2  # MSFT + TSLA (NVDA already present)
    assert [i.symbol for i in db.get_watchlist(g1.id).items] == ["NVDA", "AAPL", "MSFT"]
    assert any(g.name == "New" for g in db.list_watchlists())
