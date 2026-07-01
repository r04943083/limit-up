"""save_snapshot anti-clobber guard: a rate-limited (empty-fundamentals) fetch must never
overwrite a previously-good snapshot's fundamentals. Volatile parts (price) still refresh."""
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


def _bundle(name, pe, roe, mcap, price=100.0):
    from lucore.data.base import Fundamentals, Quote
    from lucore.services.research import ResearchBundle

    return ResearchBundle(
        symbol="MSFT", market="US",
        quote=Quote(symbol="MSFT", market="US", price=price, currency="USD", name=name),
        fundamentals=Fundamentals(symbol="MSFT", market="US", name=name, pe_ttm=pe, roe=roe,
                                  market_cap=mcap, currency="USD"),
        technical_latest={"price": price}, technical_trend="uptrend", technical_signals=[],
        news=[], spark=[], generated_at=dt.datetime.now(dt.timezone.utc),
    )


def test_empty_does_not_clobber_good(db):
    from lucore.services import research

    research.save_snapshot(_bundle("Microsoft", 30.0, 0.4, 2e12, price=300))
    # rate-limited refetch: price comes through but fundamentals are throttled to empty.
    research.save_snapshot(_bundle(None, None, None, None, price=310))
    snap = research.load_snapshot("MSFT")
    assert snap.fundamentals.name == "Microsoft"  # good fundamentals preserved
    assert snap.fundamentals.pe_ttm == 30.0
    assert snap.quote.price == 310  # volatile parts still refreshed


def test_good_overwrites_anything(db):
    from lucore.services import research

    research.save_snapshot(_bundle(None, None, None, None))
    research.save_snapshot(_bundle("Microsoft", 28.0, 0.35, 2e12))
    snap = research.load_snapshot("MSFT")
    assert snap.fundamentals.pe_ttm == 28.0  # a populated fetch always wins


def test_first_write_empty_is_kept(db):
    from lucore.services import research

    research.save_snapshot(_bundle(None, None, None, None, price=50))
    snap = research.load_snapshot("MSFT")
    assert snap is not None and snap.quote.price == 50  # nothing prior to preserve → keep it


def test_partial_throttle_keeps_prior_block(db):
    """A partial throttle — name comes back but market cap / PE / ROE are all gone — matches
    the throttle signature (mcap+PE+ROE all None) and must keep the prior good fundamentals,
    not blank them (the old all-or-nothing guard, keyed on name too, missed this)."""
    from lucore.services import research

    research.save_snapshot(_bundle("Microsoft", 30.0, 0.4, 2e12, price=300))
    research.save_snapshot(_bundle("Microsoft", None, None, None, price=310))  # throttled
    snap = research.load_snapshot("MSFT")
    assert snap.fundamentals.pe_ttm == 30.0   # kept from prior good snapshot
    assert snap.fundamentals.roe == 0.4
    assert snap.fundamentals.market_cap == 2e12
    assert snap.quote.price == 310            # volatile part still refreshed


def test_legit_field_clear_is_not_resurrected(db):
    """A single field going None on a *healthy* fetch (dividend cut, swing to a loss, dropped
    coverage) MUST overwrite the stale cached value — the guard only fires when market cap AND
    PE AND ROE are all absent, so a lone cleared field is never resurrected from cache."""
    import datetime as dt

    from lucore.data.base import Fundamentals, Quote
    from lucore.services import research
    from lucore.services.research import ResearchBundle

    def bundle(divy):
        return ResearchBundle(
            symbol="MSFT", market="US",
            quote=Quote(symbol="MSFT", market="US", price=300, currency="USD", name="Microsoft"),
            fundamentals=Fundamentals(symbol="MSFT", market="US", name="Microsoft", pe_ttm=30.0,
                                      roe=0.4, market_cap=2e12, dividend_yield=divy, currency="USD"),
            technical_latest={"price": 300}, technical_trend="uptrend", technical_signals=[],
            news=[], spark=[], generated_at=dt.datetime.now(dt.timezone.utc),
        )

    research.save_snapshot(bundle(0.008))  # previously paid a dividend
    research.save_snapshot(bundle(None))   # dividend cut — healthy fetch (mcap/PE/ROE present)
    snap = research.load_snapshot("MSFT")
    assert snap.fundamentals.dividend_yield is None  # cleared, NOT resurrected from cache
    assert snap.fundamentals.pe_ttm == 30.0          # the rest stays correct


def test_priceless_quote_keeps_last_good_price(db):
    """A quote that returns without a price (throttled) must not blank the cached price."""
    from lucore.services import research

    research.save_snapshot(_bundle("Microsoft", 30.0, 0.4, 2e12, price=300))
    research.save_snapshot(_bundle("Microsoft", 31.0, 0.4, 2e12, price=None))
    snap = research.load_snapshot("MSFT")
    assert snap.quote.price == 300            # last-good price preserved
    assert snap.fundamentals.pe_ttm == 31.0   # fundamentals still updated
