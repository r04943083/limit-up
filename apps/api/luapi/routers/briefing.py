"""Daily briefing + watchlist health routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

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
    try:
        return generate_briefing()
    except Exception as e:  # noqa: BLE001 - LLM/CLI failure → 502, consistent with other AI POSTs
        raise HTTPException(status_code=502, detail=f"briefing generation failed: {e}") from e


@router.get("/health", response_model=list[HealthOut])
def health() -> list[HealthOut]:
    """Deterministic per-watchlist-item health scores (recomputed from snapshots)."""
    return compute_watchlist_health()
