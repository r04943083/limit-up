"""TTL + single-flight primitives: concurrent misses for the same key collapse to one
computation; a fresh cache entry is reused; SingleFlight dedupes without caching."""
import threading
import time

from lucore.services.livecache import SingleFlight, TTLSingleFlight


def test_ttl_cache_reuses_within_ttl():
    c = TTLSingleFlight(ttl=10.0)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return calls["n"]

    assert c.get("k", fn) == 1
    assert c.get("k", fn) == 1  # cached
    assert calls["n"] == 1


def test_ttl_cache_expires():
    c = TTLSingleFlight(ttl=0.05)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return calls["n"]

    assert c.get("k", fn) == 1
    time.sleep(0.08)
    assert c.get("k", fn) == 2


def test_single_flight_collapses_concurrent_misses():
    c = TTLSingleFlight(ttl=10.0)
    calls = {"n": 0}
    start = threading.Barrier(8)

    def fn():
        calls["n"] += 1
        time.sleep(0.2)  # hold the flight so the others queue behind the leader
        return "v"

    results = []
    lock = threading.Lock()

    def worker():
        start.wait()
        r = c.get("hot", fn)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == ["v"] * 8
    assert calls["n"] == 1  # eight concurrent viewers → one upstream fetch


def test_single_flight_no_cache_dedups_concurrent():
    sf = SingleFlight()
    calls = {"n": 0}
    start = threading.Barrier(5)

    def fn():
        calls["n"] += 1
        time.sleep(0.2)
        return calls["n"]

    out = []
    lock = threading.Lock()

    def worker():
        start.wait()
        r = sf.do("sym", fn)
        with lock:
            out.append(r)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls["n"] == 1  # deduped
    assert out == [1] * 5  # all share the leader's result

    # A later call (not concurrent) runs fresh — SingleFlight does not cache.
    assert sf.do("sym", fn) == 2


def test_intraday_session_classification_us():
    import datetime as dt
    from zoneinfo import ZoneInfo

    from lucore.markets import Market
    from lucore.services.intraday import _session_of

    ny = ZoneInfo("America/New_York")
    pre = dt.datetime(2026, 6, 30, 8, 0, tzinfo=ny)     # 08:00 ET → pre-market
    reg = dt.datetime(2026, 6, 30, 11, 0, tzinfo=ny)    # 11:00 ET → regular
    post = dt.datetime(2026, 6, 30, 18, 0, tzinfo=ny)   # 18:00 ET → after-hours
    assert _session_of(pre, Market.US) == "pre"
    assert _session_of(reg, Market.US) == "reg"
    assert _session_of(post, Market.US) == "post"
