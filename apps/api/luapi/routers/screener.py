"""Screener + universe-seeding routes.

`/screener/*` runs the deterministic filter over cached snapshots. `/screener/universe/*`
seeds the universe from index constituents and fills snapshots in the background.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from lucore.data.universe import INDICES
from lucore.services.screener import FIELDS, FieldDef, ScreenResult, ScreenSpec, run_screen
from lucore.services.universe_seed import (
    SeedResult,
    seed_indices,
    seed_progress,
    start_financials_fill,
    start_snapshot_fill,
)

router = APIRouter(prefix="/screener", tags=["screener"])


class IndexInfo(BaseModel):
    key: str
    label: str
    market: str


class ScreenerMeta(BaseModel):
    fields: list[FieldDef]
    indices: list[IndexInfo]


@router.get("/meta", response_model=ScreenerMeta)
def meta() -> ScreenerMeta:
    """Field catalogue + seedable indices — drives the screener UI."""
    return ScreenerMeta(
        fields=FIELDS,
        indices=[IndexInfo(key=i.key, label=i.label, market=i.market) for i in INDICES],
    )


@router.post("/run", response_model=ScreenResult)
def run(spec: ScreenSpec) -> ScreenResult:
    """Apply the filter spec over every cached snapshot and return matches."""
    return run_screen(spec)


class SeedRequest(BaseModel):
    keys: list[str]
    fill: bool = True  # also start the background snapshot fill


class SeedResponse(BaseModel):
    seed: SeedResult
    progress: dict


@router.post("/universe/seed", response_model=SeedResponse)
def seed(req: SeedRequest) -> SeedResponse:
    """Upsert the chosen indices' constituents as Stock rows, then (optionally) kick the
    background snapshot fill so the screener gains data over the next minutes."""
    result = seed_indices(req.keys)
    progress = start_snapshot_fill(only_missing=True) if req.fill else seed_progress()
    return SeedResponse(seed=result, progress=progress)


@router.get("/universe/progress")
def progress(kind: str = "snapshot") -> dict:
    """Background fill progress (poll while seeding). kind = snapshot | financials."""
    return seed_progress(kind if kind in ("snapshot", "financials") else "snapshot")


@router.post("/universe/fill-financials")
def fill_financials() -> dict:
    """Start the background financials + profile fill for the whole pool (so the valuation
    band / percentile become available pool-wide). Heavy; poll progress with kind=financials."""
    return start_financials_fill(only_missing=True)
