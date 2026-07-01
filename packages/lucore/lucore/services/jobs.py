"""In-process async job runner for long AI calls: submit → poll.

Long `claude -p` calls (60–180s) held open as a single HTTP request are fragile over
proxies and flaky networks, and they pin a server thread the whole time. Instead, submit
returns a job_id immediately; the heavy work runs on a small background pool (still bounded
by the global llm_slot() semaphore) and the client polls /jobs/{id} for the result.

Results live in memory with a TTL sweep. This is single-process only (fine for the current
single-worker deploy); multi-worker would need a shared store (Phase 7).
"""
from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel


class Job(BaseModel):
    id: str
    kind: str
    status: str  # pending | running | done | error
    result: Any | None = None
    error: str | None = None
    created_at: float
    updated_at: float


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lu-job")
_TTL = 1800.0  # keep finished jobs 30 min so a slow poller can still collect the result


def _sweep(now: float) -> None:
    dead = [
        jid for jid, j in _jobs.items()
        if j.status in ("done", "error") and now - j.updated_at > _TTL
    ]
    for jid in dead:
        _jobs.pop(jid, None)


def _run(job_id: str, fn: Callable[[], Any]) -> None:
    with _lock:
        j = _jobs.get(job_id)
        if j is None:
            return
        j.status = "running"
        j.updated_at = time.time()
    try:
        result = fn()
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="json")
        with _lock:
            j = _jobs.get(job_id)
            if j is not None:
                j.status = "done"
                j.result = result
                j.updated_at = time.time()
    except Exception as e:  # noqa: BLE001 - capture any failure into the job record
        with _lock:
            j = _jobs.get(job_id)
            if j is not None:
                j.status = "error"
                j.error = str(e)
                j.updated_at = time.time()


def submit(kind: str, fn: Callable[[], Any]) -> Job:
    """Enqueue `fn` to run on the background pool; return the pending Job immediately."""
    now = time.time()
    job = Job(id=uuid.uuid4().hex, kind=kind, status="pending", created_at=now, updated_at=now)
    with _lock:
        _sweep(now)
        _jobs[job.id] = job
        # Snapshot the pending state *before* the worker can mutate the stored object.
        pending = job.model_copy(deep=True)
    _pool.submit(_run, job.id, fn)
    return pending


def get(job_id: str) -> Job | None:
    with _lock:
        j = _jobs.get(job_id)
        return j.model_copy(deep=True) if j is not None else None
