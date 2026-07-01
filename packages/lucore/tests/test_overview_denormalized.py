"""市场 overview 去规范化:save_snapshot 落 denormalized 列;get_overview 只读这些列
(不解析每行 JSON),对旧行做一次性回填,并有短 TTL 缓存 + sync 后失效。"""
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
    from lucore.services import markets_svc

    markets_svc.invalidate_overview()
    yield


def _bundle(symbol="NVDA", market="US", price=100.0, change_pct=2.5,
            sector="Technology", name="NVIDIA", market_cap=3.0e12):
    from lucore.data.base import Fundamentals, Quote
    from lucore.services.research import ResearchBundle

    return ResearchBundle(
        symbol=symbol,
        market=market,
        quote=Quote(symbol=symbol, market=market, price=price, change_pct=change_pct, name=name),
        fundamentals=Fundamentals(symbol=symbol, market=market, sector=sector,
                                  market_cap=market_cap, name=name),
        technical_latest={},
        technical_trend="up",
        technical_signals=[],
        news=[],
        spark=[],
        generated_at=dt.datetime.now(dt.timezone.utc),
    )


def test_save_snapshot_denormalizes_columns(db):
    from lucore.db import session_scope
    from lucore.db.models import Snapshot
    from lucore.services.research import save_snapshot

    save_snapshot(_bundle())
    with session_scope() as s:
        snap = s.get(Snapshot, "NVDA")
        assert snap.market == "US"
        assert snap.sector == "Technology"
        assert snap.price == 100.0
        assert snap.change_pct == 2.5
        assert snap.market_cap == 3.0e12
        assert snap.name == "NVIDIA"


def test_get_overview_reads_columns_without_parsing_json(db, monkeypatch):
    from lucore.services import markets_svc
    from lucore.services.research import save_snapshot

    save_snapshot(_bundle("NVDA", price=100.0, change_pct=2.5))
    save_snapshot(_bundle("AAPL", price=200.0, change_pct=-1.0, sector="Tech", name="Apple"))

    # If get_overview parses JSON it would touch ResearchBundle.model_validate_json; ensure it
    # does NOT for freshly-denormalized rows (backfill only targets market IS NULL rows).
    import lucore.services.research as research_mod
    calls = {"n": 0}
    orig = research_mod.ResearchBundle.model_validate_json.__func__

    def _counting(cls, *a, **k):
        calls["n"] += 1
        return orig(cls, *a, **k)

    monkeypatch.setattr(research_mod.ResearchBundle, "model_validate_json",
                        classmethod(_counting))

    rows = markets_svc.get_overview(force=True)
    by = {r.symbol: r for r in rows}
    assert by["NVDA"].price == 100.0 and by["NVDA"].change_pct == 2.5
    assert by["AAPL"].price == 200.0 and by["AAPL"].market == "US"
    assert calls["n"] == 0  # no JSON parsing for denormalized rows


def test_backfill_fills_legacy_rows(db):
    """A snapshot written before denormalization (market IS NULL) is back-filled once."""
    from lucore.db import session_scope
    from lucore.db.models import Snapshot
    from lucore.services import markets_svc

    b = _bundle("MSFT", price=400.0, change_pct=1.5, sector="Software", name="Microsoft")
    with session_scope() as s:
        s.add(Snapshot(symbol="MSFT", bundle_json=b.model_dump_json()))  # columns left NULL

    rows = markets_svc.get_overview(force=True)
    msft = next(r for r in rows if r.symbol == "MSFT")
    assert msft.price == 400.0 and msft.sector == "Software" and msft.market == "US"

    with session_scope() as s:
        snap = s.get(Snapshot, "MSFT")
        assert snap.market == "US" and snap.price == 400.0  # persisted, not re-derived each call


def test_blank_snapshot_excluded_from_overview(db):
    """A blank/unparseable snapshot (bundle_json empty → market stays NULL) must not surface
    as an all-None row in the overview (which would corrupt the histogram / sector heatmap)."""
    from lucore.db import session_scope
    from lucore.db.models import Snapshot
    from lucore.services import markets_svc
    from lucore.services.research import save_snapshot

    save_snapshot(_bundle("NVDA"))
    with session_scope() as s:
        s.add(Snapshot(symbol="JUNK", bundle_json=""))  # never denormalizes

    rows = markets_svc.get_overview(force=True)
    syms = {r.symbol for r in rows}
    assert "NVDA" in syms
    assert "JUNK" not in syms  # excluded, not an all-None row


def test_ttl_cache_and_invalidate(db):
    from lucore.services import markets_svc
    from lucore.services.research import save_snapshot

    save_snapshot(_bundle("NVDA"))
    first = markets_svc.get_overview(force=True)
    assert len(first) == 1

    save_snapshot(_bundle("AAPL"))
    # Within TTL, the cached (stale) result is served.
    assert len(markets_svc.get_overview()) == 1
    # After invalidation, the new symbol appears.
    markets_svc.invalidate_overview()
    assert len(markets_svc.get_overview()) == 2
