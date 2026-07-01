"""In-process scheduler (APScheduler) for LU's autonomous daily loop.

Runs on the FastAPI process: every morning it syncs tracked symbols into the DB and
writes the daily briefing — so the dashboard is fresh when the user opens it, at zero cost.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_settings

log = logging.getLogger("lu.scheduler")

_scheduler: BackgroundScheduler | None = None


def _claim_daily_run(day: str) -> bool:
    """Atomically claim today's daily run so that, if the API runs with multiple uvicorn
    workers, only ONE executes the job (others would otherwise each fire it N times). The
    unique-PK insert is the arbiter: the losing worker's commit raises IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    from ..db import session_scope
    from ..db.models import MarketDataCache

    key = f"jobclaim:daily:{day}"
    try:
        with session_scope() as s:
            if s.get(MarketDataCache, key) is not None:
                return False
            s.add(MarketDataCache(cache_key=key, payload_json="1"))
        return True
    except IntegrityError:
        return False  # another worker claimed it first


def _daily_job() -> None:
    """Sync data then generate the briefing. Imported lazily to avoid heavy import at startup."""
    from ..services.briefing import generate_briefing
    from ..services.market_cache import today_str
    from ..services.markets_svc import get_indices
    from ..services.sync import sync_all

    if not _claim_daily_run(today_str()):
        log.info("daily job already claimed by another worker — skipping")
        return

    try:
        res = sync_all()
        log.info("daily sync: %d/%d synced", res.synced, res.requested)
    except Exception:  # noqa: BLE001
        log.exception("daily sync failed")
    try:
        get_indices(force=True)  # warm the index ticker cache for the morning open
    except Exception:  # noqa: BLE001
        log.exception("index warm failed")
    try:  # warm the AI-arena benchmark's daily bars so its equity curve stays current
        from ..data.router import get_router
        from ..services.arena import BENCHMARK

        get_router().get_ohlcv(BENCHMARK[0], period="1y", interval="1d")
    except Exception:  # noqa: BLE001
        log.exception("arena benchmark warm failed")
    try:
        generate_briefing()
        log.info("daily briefing generated")
    except Exception:  # noqa: BLE001
        log.exception("daily briefing failed")


def start_scheduler() -> BackgroundScheduler | None:
    """Start the background scheduler if enabled. Idempotent."""
    global _scheduler
    s = get_settings()
    if not s.enable_scheduler or _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _daily_job,
        CronTrigger(hour=s.briefing_hour, minute=s.briefing_minute),
        id="daily_briefing",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    log.info("scheduler started — daily job at %02d:%02d", s.briefing_hour, s.briefing_minute)
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
