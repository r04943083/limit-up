"""Market-level routes: index ticker bar, market overview, and US discovery movers."""
from __future__ import annotations

from fastapi import APIRouter

from lucore.services import us_market as us_svc
from lucore.services.markets_svc import IndexQuote, OverviewRow, get_indices, get_overview

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/indices", response_model=list[IndexQuote])
def indices() -> list[IndexQuote]:
    return get_indices()


@router.get("/overview", response_model=list[OverviewRow])
def overview() -> list[OverviewRow]:
    return get_overview()


# ---- US discovery (发现/异动) — the US analogue of the A-share limit-up page ----
@router.get("/us/feeds", response_model=list[us_svc.Feed])
def us_feeds() -> list[us_svc.Feed]:
    """Available US movers feeds (kind + label) for the 发现 page tabs."""
    return us_svc.list_feeds()


@router.get("/us/movers/{kind}", response_model=us_svc.MoversResult)
def us_movers(kind: str, count: int = 30) -> us_svc.MoversResult:
    """One US movers board (day_gainers / day_losers / most_actives / …), cache-first."""
    return us_svc.get_movers(kind, count=count)
