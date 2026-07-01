"""Scheduler leader-lock: the daily run is claimed once per day (multi-worker safety)."""
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


def test_daily_run_claimed_once_per_day(db):
    from lucore.scheduler.jobs import _claim_daily_run

    assert _claim_daily_run("20250101") is True    # first worker wins
    assert _claim_daily_run("20250101") is False   # second worker skips
    assert _claim_daily_run("20250101") is False
    assert _claim_daily_run("20250102") is True    # a new day is a fresh claim
