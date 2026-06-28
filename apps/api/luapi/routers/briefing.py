"""Daily briefing + watchlist health routes."""
from __future__ import annotations

from fastapi import APIRouter

from lucore.services.briefing import (
    HealthOut,
    SavedBriefing,
    compute_watchlist_health,
    generate_briefing,
    latest_briefing,
)

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.get("", response_model=SavedBriefing | None)
def get_briefing() -> SavedBriefing | None:
    return latest_briefing()


@router.post("/generate", response_model=SavedBriefing)
def generate() -> SavedBriefing:
    """Assemble today's facts and write the AI briefing (claude -p). ~30-60s."""
    return generate_briefing()


@router.get("/health", response_model=list[HealthOut])
def health() -> list[HealthOut]:
    """Deterministic per-watchlist-item health scores (recomputed from snapshots)."""
    return compute_watchlist_health()
