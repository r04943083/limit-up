"""Short-TTL cache + single-flight for hot *live* endpoints (quote / intraday) and
request de-duplication for cold research fetches.

Two problems this solves under concurrent use:
  1. A burst of viewers on the same symbol each hit yfinance separately — slow and a fast
     path to rate-limiting. A tiny TTL cache collapses repeats within a few seconds.
  2. Even without a cache (cold research), N concurrent requests for the same uncached
     symbol each run a full live fetch + write the same snapshot row. Single-flight makes
     the first request do the work and the rest wait on and share its result.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")


class TTLSingleFlight:
    """Per-key TTL cache with single-flight: concurrent misses for the same key collapse
    to one computation whose result the waiters share."""

    def __init__(self, ttl: float, wait_timeout: float = 30.0) -> None:
        self.ttl = ttl
        self.wait_timeout = wait_timeout
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, _T]] = {}
        self._inflight: dict[str, threading.Event] = {}

    def _fresh(self, key: str) -> tuple[bool, _T | None]:
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.ttl:
            return True, hit[1]
        return False, None

    def get(self, key: str, fn: Callable[[], _T]) -> _T:
        with self._lock:
            ok, val = self._fresh(key)
            if ok:
                return val  # type: ignore[return-value]
            ev = self._inflight.get(key)
            leader = ev is None
            if leader:
                ev = threading.Event()
                self._inflight[key] = ev

        if not leader:
            ev.wait(timeout=self.wait_timeout)  # type: ignore[union-attr]
            with self._lock:
                ok, val = self._fresh(key)
            if ok:
                return val  # type: ignore[return-value]
            return fn()  # leader failed or result expired — compute ourselves (rare)

        try:
            val = fn()
            with self._lock:
                self._cache[key] = (time.time(), val)
            return val
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            ev.set()  # type: ignore[union-attr]

    def invalidate(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._cache.clear()
            else:
                self._cache.pop(key, None)


class SingleFlight:
    """De-duplicate concurrent calls for the same key WITHOUT caching the result
    (used where a durable cache already exists downstream, e.g. the snapshot table)."""

    def __init__(self, wait_timeout: float = 60.0) -> None:
        self.wait_timeout = wait_timeout
        self._lock = threading.Lock()
        self._inflight: dict[str, tuple[threading.Event, list]] = {}

    def do(self, key: str, fn: Callable[[], _T]) -> _T:
        with self._lock:
            entry = self._inflight.get(key)
            leader = entry is None
            if leader:
                entry = (threading.Event(), [])  # (done, [result])
                self._inflight[key] = entry

        ev, box = entry  # type: ignore[misc]
        if not leader:
            ev.wait(timeout=self.wait_timeout)
            if box:  # leader stored a result
                return box[0]
            return fn()  # leader errored — fall back to our own attempt

        try:
            val = fn()
            box.append(val)
            return val
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            ev.set()


# Hot live endpoints. Quotes tick fast but a few seconds of staleness is invisible;
# intraday has many bars and is heavier, so a slightly longer TTL.
_quote_cache: TTLSingleFlight = TTLSingleFlight(ttl=15.0)
_intraday_cache: TTLSingleFlight = TTLSingleFlight(ttl=30.0)
_research_flight: SingleFlight = SingleFlight()


def cached_quote(symbol: str, fn: Callable[[], _T]) -> _T:
    return _quote_cache.get(symbol.upper(), fn)


def cached_intraday(symbol: str, rng: str, prepost: bool, fn: Callable[[], _T]) -> _T:
    return _intraday_cache.get(f"{symbol.upper()}:{rng}:{int(prepost)}", fn)


def research_single_flight(symbol: str, fn: Callable[[], _T]) -> _T:
    return _research_flight.do(symbol.upper(), fn)
