"""Deep one-click sync: snapshot pass + financials/profile gap-fill + global feeds.

All network-bound calls are monkeypatched, so this verifies *wiring* (what gets called
and how counts are tallied), not live fetching.
"""
import lucore.services.cn_market as cn
import lucore.services.financials as fin
import lucore.services.markets_svc as mk
import lucore.services.profile as prof
import lucore.services.sync as sync
import lucore.services.us_market as us_svc


def _patch_common(monkeypatch, *, fin_ok=True, prof_ok=True):
    monkeypatch.setattr(sync, "tracked_symbols", lambda: ["AAA", "BBB"])
    # snapshot pass: make per-symbol build succeed without network
    monkeypatch.setattr(sync, "build_research_bundle", lambda s: object())

    def _fin(symbol, *a, **k):  # noqa: ANN001
        if not fin_ok:
            raise RuntimeError("no statements")
        return object()

    def _prof(symbol, *a, **k):  # noqa: ANN001
        if not prof_ok:
            raise RuntimeError("no profile")
        return object()

    monkeypatch.setattr(fin, "get_financials_cached", _fin)
    monkeypatch.setattr(prof, "get_profile_cached", _prof)
    monkeypatch.setattr(mk, "get_indices", lambda force=False: [])
    monkeypatch.setattr(cn, "get_limit_up_pool", lambda *a, **k: object())
    monkeypatch.setattr(cn, "get_dragon_tiger", lambda *a, **k: object())
    monkeypatch.setattr(cn, "get_hsgt_summary", lambda *a, **k: object())
    # US discovery movers are warmed too; patch so no live yfinance in the wiring test.
    monkeypatch.setattr(us_svc, "get_movers", lambda *a, **k: object())


def test_deep_sync_fills_fundamentals_and_feeds(monkeypatch):
    _patch_common(monkeypatch)
    r = sync.sync_all(deep=True)
    assert r.requested == 2
    assert r.synced == 2
    assert r.financials_synced == 2
    assert r.profiles_synced == 2
    assert r.feeds == {"indices": True, "limit_up": True, "dragon_tiger": True, "hsgt": True,
                       "us_day_gainers": True, "us_day_losers": True, "us_most_actives": True}


def test_shallow_sync_skips_fundamentals(monkeypatch):
    _patch_common(monkeypatch)
    r = sync.sync_all(deep=False)
    assert r.financials_synced == 0
    assert r.profiles_synced == 0
    # global feeds still refresh even in shallow mode (they're cheap + high value)
    assert set(r.feeds) == {"indices", "limit_up", "dragon_tiger", "hsgt",
                            "us_day_gainers", "us_day_losers", "us_most_actives"}


def test_failed_fundamentals_are_tolerated(monkeypatch):
    _patch_common(monkeypatch, fin_ok=False, prof_ok=True)
    r = sync.sync_all(deep=True)
    assert r.financials_synced == 0   # both raised → counted as not synced
    assert r.profiles_synced == 2     # profiles still succeeded
    assert r.synced == 2              # snapshot pass unaffected


def test_fresh_symbols_are_skipped(tmp_path, monkeypatch):
    """A symbol synced within max_age_hours is skipped; stale/missing ones still sync."""
    import datetime as dt

    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None
    from lucore.db import init_db, session_scope
    from lucore.db.models import Snapshot

    init_db()
    now = dt.datetime.now(dt.timezone.utc)
    with session_scope() as s:
        s.add(Snapshot(symbol="AAA", bundle_json="{}", synced_at=now))                       # fresh
        s.add(Snapshot(symbol="BBB", bundle_json="{}", synced_at=now - dt.timedelta(days=2)))  # stale

    _patch_common(monkeypatch)
    synced_syms: list[str] = []
    real = sync.sync_symbols
    monkeypatch.setattr(sync, "sync_symbols", lambda syms, **k: (synced_syms.extend(syms) or real(syms, **k)))

    r = sync.sync_all(deep=False, max_age_hours=6.0)
    assert "AAA" not in synced_syms        # fresh → skipped
    assert "BBB" in synced_syms            # stale → synced
    assert r.skipped_fresh == 1
    assert r.requested == 2                # still reports against everything tracked


def test_max_age_zero_forces_full(tmp_path, monkeypatch):
    import datetime as dt

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
        s.add(Snapshot(symbol="AAA", bundle_json="{}", synced_at=dt.datetime.now(dt.timezone.utc)))

    _patch_common(monkeypatch)
    r = sync.sync_all(deep=False, max_age_hours=0)
    assert r.skipped_fresh == 0  # forced full refresh ignores freshness


def test_failing_feed_marked_false(monkeypatch):
    _patch_common(monkeypatch)

    def _boom(*a, **k):  # noqa: ANN001
        raise RuntimeError("source down")

    monkeypatch.setattr(cn, "get_hsgt_summary", _boom)
    r = sync.sync_all(deep=True)
    assert r.feeds["hsgt"] is False
    assert r.feeds["indices"] is True
