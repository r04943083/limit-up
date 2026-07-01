"""Global throttle for LLM subprocess calls.

Every `claude -p` forks a full Claude Code process that draws on one shared Max-plan
quota. Under concurrent use (multiple viewers triggering AI at once, or the arena running
several personas) an unbounded fan-out would spawn many heavy subprocesses and trip rate
limits. A single process-wide bounded semaphore serializes them down to a safe width;
callers past the cap block until a slot frees (fair queueing), they don't fail.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from ..config import get_settings

_lock = threading.Lock()
_sem: threading.BoundedSemaphore | None = None
_configured_width: int | None = None


def _get_semaphore() -> threading.BoundedSemaphore:
    global _sem, _configured_width
    with _lock:
        width = get_settings().llm_max_concurrency
        # Rebuild if the configured width changed (e.g. tests tweak settings).
        if _sem is None or _configured_width != width:
            _sem = threading.BoundedSemaphore(width)
            _configured_width = width
        return _sem


class LLMBusyError(RuntimeError):
    """Raised when no LLM slot frees up within the wait budget (avoids an unbounded hang)."""


@contextmanager
def llm_slot(timeout: float | None = None) -> Iterator[None]:
    """Acquire one LLM concurrency slot for the duration of the block.

    `timeout` bounds how long we queue for a free slot (so total latency stays bounded to
    ~queue-wait + run-time rather than growing without limit under a burst). On timeout we
    raise LLMBusyError instead of hanging indefinitely; None waits forever (legacy).
    """
    sem = _get_semaphore()
    acquired = sem.acquire() if timeout is None else sem.acquire(timeout=timeout)
    if not acquired:
        raise LLMBusyError("LLM 并发已满,请稍后重试")
    try:
        yield
    finally:
        sem.release()
