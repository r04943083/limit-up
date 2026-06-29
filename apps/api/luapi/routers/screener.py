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
def progress() -> dict:
    """Background snapshot-fill progress (poll while seeding)."""
    return seed_progress()
