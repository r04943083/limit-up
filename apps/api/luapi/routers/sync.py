"""Data-sync routes — one-click 'update everything into the DB' for fast loads."""
from __future__ import annotations

from fastapi import APIRouter

from lucore.services.sync import FreshnessRow, SyncResult, freshness, sync_all

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/all", response_model=SyncResult)
def sync_everything() -> SyncResult:
    """Refresh every tracked symbol (watchlist + portfolio) into the DB."""
    return sync_all()


@router.get("/freshness", response_model=list[FreshnessRow])
def get_freshness() -> list[FreshnessRow]:
    return freshness()
