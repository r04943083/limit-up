"""Async job runner: submit returns immediately; poll transitions to done/error; a
BaseModel result is JSON-dumped so the /jobs response can carry it."""
import time

from pydantic import BaseModel

from lucore.services import jobs as jobs_svc


def _wait(job_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = jobs_svc.get(job_id)
        if j and j.status in ("done", "error"):
            return j
        time.sleep(0.01)
    raise AssertionError("job did not finish in time")


def test_submit_runs_and_returns_result():
    job = jobs_svc.submit("t", lambda: {"answer": 42})
    assert job.status in ("pending", "running")
    done = _wait(job.id)
    assert done.status == "done"
    assert done.result == {"answer": 42}
    assert done.error is None


def test_basemodel_result_is_dumped():
    class Out(BaseModel):
        name: str
        score: float

    job = jobs_svc.submit("t", lambda: Out(name="NVDA", score=7.5))
    done = _wait(job.id)
    assert done.status == "done"
    assert done.result == {"name": "NVDA", "score": 7.5}  # dumped to a plain dict


def test_error_is_captured():
    def boom():
        raise RuntimeError("nope")

    job = jobs_svc.submit("t", boom)
    done = _wait(job.id)
    assert done.status == "error"
    assert "nope" in done.error


def test_unknown_job_is_none():
    assert jobs_svc.get("does-not-exist") is None
