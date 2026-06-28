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


def _daily_job() -> None:
    """Sync data then generate the briefing. Imported lazily to avoid heavy import at startup."""
    from ..services.briefing import generate_briefing
    from ..services.sync import sync_all

    try:
        res = sync_all()
        log.info("daily sync: %d/%d synced", res.synced, res.requested)
    except Exception:  # noqa: BLE001
        log.exception("daily sync failed")
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
