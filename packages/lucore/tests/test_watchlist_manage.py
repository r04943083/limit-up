"""Watchlist management: ordering, rename/delete, move, tags (no network).

`add_item` calls ensure_stock which would normally hit the network; we monkeypatch it
to a no-op so these stay pure DB tests of the ordering/move/tag logic.
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

    # Offline stand-in for ensure_stock: create a minimal Stock row (satisfies the FK)
    # without any network fundamentals lookup.
    def _ensure(symbol, name=None, **fields):  # noqa: ANN001
        with session_scope() as s:
            if s.get(Stock, symbol) is None:
                s.add(Stock(symbol=symbol, market="US", name=name or symbol))

    import lucore.services.watchlist as wl

    monkeypatch.setattr(wl, "ensure_stock", _ensure)
    return wl


def test_sort_order_on_add_and_reorder(db):
    g = db.create_watchlist("US")
    for sym in ["NVDA", "AAPL", "MSFT"]:
        db.add_item(g.id, sym)
    items = db.get_watchlist(g.id).items
    assert [i.symbol for i in items] == ["NVDA", "AAPL", "MSFT"]

    # Reverse the order and persist.
    db.reorder_items(g.id, [items[2].id, items[1].id, items[0].id])
    items2 = db.get_watchlist(g.id).items
    assert [i.symbol for i in items2] == ["MSFT", "AAPL", "NVDA"]


def test_group_reorder_and_rename_delete(db):
    a = db.create_watchlist("A")
    b = db.create_watchlist("B")
    c = db.create_watchlist("C")
    assert [g.name for g in db.list_watchlists()] == ["A", "B", "C"]

    db.reorder_watchlists([c.id, a.id, b.id])
    assert [g.name for g in db.list_watchlists()] == ["C", "A", "B"]

    db.rename_watchlist(a.id, "Alpha")
    assert any(g.name == "Alpha" for g in db.list_watchlists())

    assert db.delete_watchlist(b.id) is True
    assert all(g.id != b.id for g in db.list_watchlists())


def test_move_item_between_groups_merges(db):
    g1 = db.create_watchlist("G1")
    g2 = db.create_watchlist("G2")
    it = db.add_item(g1.id, "NVDA")
    db.add_item(g2.id, "AAPL")

    # Move NVDA from G1 to G2.
    assert db.move_item(it.id, g2.id) is True
    assert [i.symbol for i in db.get_watchlist(g1.id).items] == []
    assert {i.symbol for i in db.get_watchlist(g2.id).items} == {"AAPL", "NVDA"}

    # Moving a duplicate symbol into a group that already has it just drops the source.
    dup = db.add_item(g1.id, "AAPL")
    assert db.move_item(dup.id, g2.id) is True
    assert [i.symbol for i in db.get_watchlist(g1.id).items] == []
    assert len(db.get_watchlist(g2.id).items) == 2  # no duplicate AAPL


def test_update_item_tags_normalized(db):
    g = db.create_watchlist("T")
    it = db.add_item(g.id, "NVDA")
    out = db.update_item(it.id, tags=" ai , chip ,, ai , semis ")
    # trimmed, de-duped, order preserved
    assert out.tags == "ai,chip,semis"
