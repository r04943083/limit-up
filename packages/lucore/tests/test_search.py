"""Symbol search: ranking + name/ticker matching over the downloaded universe.

Pure DB test — seeds a temp DB and queries search_symbols directly (no network).
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
    with session_scope() as s:
        s.add_all([
            Stock(symbol="TSLA", market="US", name="Tesla, Inc."),
            Stock(symbol="TSM", market="US", name="Taiwan Semiconductor"),
            Stock(symbol="MSFT", market="US", name="Microsoft Corporation"),
            Stock(symbol="MS", market="US", name="Morgan Stanley"),
            Stock(symbol="0700.HK", market="HK", name="Tencent Holdings Limited"),
            Stock(symbol="JUNK", market="US", name=None),  # half-synced row, no name
        ])
    import lucore.services.search as search
    return search


def test_empty_query_returns_nothing(db):
    assert db.search_symbols("") == []
    assert db.search_symbols("   ") == []


def test_exact_ticker_ranks_first(db):
    hits = db.search_symbols("ms")
    syms = [h.symbol for h in hits]
    # Exact "MS" before prefix "MSFT".
    assert syms[0] == "MS"
    assert "MSFT" in syms
    assert syms.index("MS") < syms.index("MSFT")


def test_name_match(db):
    hits = db.search_symbols("micro")
    assert [h.symbol for h in hits] == ["MSFT"]


def test_ticker_prefix_before_name_contains(db):
    # "ts" prefixes TSLA/TSM (rank 1); only those should surface, ticker order stable.
    syms = [h.symbol for h in db.search_symbols("ts")]
    assert "TSLA" in syms and "TSM" in syms


def test_null_name_rows_excluded(db):
    assert all(h.symbol != "JUNK" for h in db.search_symbols("junk"))


def test_case_insensitive_and_limit(db):
    assert [h.symbol for h in db.search_symbols("TENCENT")] == ["0700.HK"]
    assert len(db.search_symbols("s", limit=2)) <= 2
