"""Market-level routes: index ticker bar for the status strip."""
from __future__ import annotations

from fastapi import APIRouter

from lucore.services.markets_svc import IndexQuote, OverviewRow, get_indices, get_overview

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/indices", response_model=list[IndexQuote])
def indices() -> list[IndexQuote]:
    return get_indices()


@router.get("/overview", response_model=list[OverviewRow])
def overview() -> list[OverviewRow]:
    return get_overview()
