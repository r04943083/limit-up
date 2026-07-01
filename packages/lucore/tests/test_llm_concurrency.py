"""Global LLM slot caps concurrent subprocess width so a burst of AI requests can't
fork-bomb the host / trip the shared Max-plan quota."""
import threading
import time


def _reset_settings(monkeypatch, width: int):
    monkeypatch.setenv("LU_LLM_MAX_CONCURRENCY", str(width))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.llm.concurrency as conc

    conc._sem = None
    conc._configured_width = None


def test_llm_slot_caps_concurrency(monkeypatch):
    _reset_settings(monkeypatch, 2)
    from lucore.llm.concurrency import llm_slot

    active = {"n": 0, "peak": 0}
    lock = threading.Lock()
    start = threading.Barrier(6)

    def worker():
        start.wait()
        with llm_slot():
            with lock:
                active["n"] += 1
                active["peak"] = max(active["peak"], active["n"])
            time.sleep(0.15)
            with lock:
                active["n"] -= 1

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert active["peak"] <= 2  # never more than the configured width run at once


def test_llm_slot_times_out_when_full(monkeypatch):
    _reset_settings(monkeypatch, 1)
    from lucore.llm.concurrency import LLMBusyError, llm_slot

    import pytest

    with llm_slot():  # occupy the only slot
        with pytest.raises(LLMBusyError):
            with llm_slot(timeout=0.1):  # can't get a slot in time → raises, doesn't hang
                pass


def test_llm_slot_none_timeout_blocks_then_succeeds(monkeypatch):
    _reset_settings(monkeypatch, 1)
    import threading
    import time

    from lucore.llm.concurrency import llm_slot

    got = []

    def waiter():
        with llm_slot():  # no timeout → blocks until the holder releases
            got.append(True)

    holder_done = threading.Event()

    def holder():
        with llm_slot():
            time.sleep(0.15)
        holder_done.set()

    h = threading.Thread(target=holder)
    w = threading.Thread(target=waiter)
    h.start()
    time.sleep(0.02)  # ensure holder grabs the slot first
    w.start()
    h.join()
    w.join()
    assert got == [True]  # the waiter eventually acquired, did not error


def test_llm_slot_rebuilds_on_width_change(monkeypatch):
    _reset_settings(monkeypatch, 1)
    from lucore.llm.concurrency import _get_semaphore

    assert _get_semaphore()._initial_value == 1
    _reset_settings(monkeypatch, 3)
    assert _get_semaphore()._initial_value == 3
