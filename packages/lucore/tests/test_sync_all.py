"""Deep one-click sync: snapshot pass + financials/profile gap-fill + global feeds.

All network-bound calls are monkeypatched, so this verifies *wiring* (what gets called
and how counts are tallied), not live fetching.
"""
import lucore.services.cn_market as cn
import lucore.services.financials as fin
import lucore.services.markets_svc as mk
import lucore.services.profile as prof
import lucore.services.sync as sync


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


def test_deep_sync_fills_fundamentals_and_feeds(monkeypatch):
    _patch_common(monkeypatch)
    r = sync.sync_all(deep=True)
    assert r.requested == 2
    assert r.synced == 2
    assert r.financials_synced == 2
    assert r.profiles_synced == 2
    assert r.feeds == {"indices": True, "limit_up": True, "dragon_tiger": True, "hsgt": True}


def test_shallow_sync_skips_fundamentals(monkeypatch):
    _patch_common(monkeypatch)
    r = sync.sync_all(deep=False)
    assert r.financials_synced == 0
    assert r.profiles_synced == 0
    # global feeds still refresh even in shallow mode (they're cheap + high value)
    assert set(r.feeds) == {"indices", "limit_up", "dragon_tiger", "hsgt"}


def test_failed_fundamentals_are_tolerated(monkeypatch):
    _patch_common(monkeypatch, fin_ok=False, prof_ok=True)
    r = sync.sync_all(deep=True)
    assert r.financials_synced == 0   # both raised → counted as not synced
    assert r.profiles_synced == 2     # profiles still succeeded
    assert r.synced == 2              # snapshot pass unaffected


def test_failing_feed_marked_false(monkeypatch):
    _patch_common(monkeypatch)

    def _boom(*a, **k):  # noqa: ANN001
        raise RuntimeError("source down")

    monkeypatch.setattr(cn, "get_hsgt_summary", _boom)
    r = sync.sync_all(deep=True)
    assert r.feeds["hsgt"] is False
    assert r.feeds["indices"] is True
