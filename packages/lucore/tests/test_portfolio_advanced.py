"""Advanced portfolio services: Brinson attribution + TLH scan over the real holdings."""
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


def _snap(symbol, price, sector="Tech"):
    from lucore.data.base import Fundamentals, Quote
    from lucore.services.research import ResearchBundle, save_snapshot

    save_snapshot(ResearchBundle(
        symbol=symbol, market="US",
        quote=Quote(symbol=symbol, market="US", price=price),
        fundamentals=Fundamentals(symbol=symbol, market="US", sector=sector),
        technical_latest={}, technical_trend="up", technical_signals=[], news=[], spark=[],
        generated_at=dt.datetime.now(dt.timezone.utc),
    ))


def test_attribution_identity_holds(db, monkeypatch):
    from lucore.services import portfolio as pf
    from lucore.services import portfolio_advanced as pa

    pid = pf.ensure_default_portfolio()
    pf.upsert_holding(pid, "AAA", 10, 90.0)
    pf.upsert_holding(pid, "BBB", 10, 90.0)
    pf.upsert_holding(pid, "CCC", 10, 90.0)

    bundles = {
        "AAA": ("Tech", 100.0), "BBB": ("Tech", 200.0), "CCC": ("Health", 50.0),
    }

    class _RB:
        def __init__(self, sector, price):
            from lucore.data.base import Fundamentals, Quote
            self.fundamentals = Fundamentals(symbol="x", market="US", sector=sector)
            self.quote = Quote(symbol="x", market="US", price=price)

    monkeypatch.setattr(pa, "get_research", lambda s, cached=True: _RB(*bundles[s]))
    monkeypatch.setattr(pa, "_period_return", lambda s, period="1y": {"AAA": 0.10, "BBB": 0.05, "CCC": 0.02}[s])

    res = pa.compute_attribution(pid)
    assert res.ok
    a = res.attribution
    assert {seg.segment for seg in a.segments} == {"Tech", "Health"}
    # BHB identity: the three effects sum to the total active return.
    assert round(a.allocation_pct + a.selection_pct + a.interaction_pct, 2) == a.total_active_pct


def test_tlh_scan_over_holdings(db):
    from lucore.services import portfolio as pf
    from lucore.services import portfolio_advanced as pa

    pid = pf.ensure_default_portfolio()
    pf.upsert_holding(pid, "LOSS", 10, 100.0)   # cost 100, price 80 → loss
    pf.upsert_holding(pid, "GAIN", 10, 100.0)   # cost 100, price 120 → excluded
    _snap("LOSS", 80.0)
    _snap("GAIN", 120.0)

    res = pa.compute_tlh(pid)
    assert res.ok
    cands = res.result.candidates
    assert [c.symbol for c in cands] == ["LOSS"]
    assert res.result.total_harvestable_loss == 200.0
    # Just-added holding → within the 30-day wash-sale window.
    assert cands[0].wash_sale_risk is True


def test_attribution_needs_two_holdings(db):
    from lucore.services import portfolio as pf
    from lucore.services import portfolio_advanced as pa

    pid = pf.ensure_default_portfolio()
    pf.upsert_holding(pid, "AAA", 10, 90.0)
    assert pa.compute_attribution(pid).ok is False
