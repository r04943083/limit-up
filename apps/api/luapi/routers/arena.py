"""AI 竞技场 routes (#8 + #13): persona-driven paper accounts that compete.

GET  /arena          → leaderboard + equity curves + benchmark
POST /arena/tick     → run one rebalance round (every persona trades; calls the LLM)
POST /arena/reset    → wipe AI accounts back to starting cash
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.services import arena

router = APIRouter(prefix="/arena", tags=["arena"])


@router.get("", response_model=arena.ArenaOut)
def overview() -> arena.ArenaOut:
    return arena.get_arena()


@router.post("/tick", response_model=arena.ArenaOut)
def tick() -> arena.ArenaOut:
    try:
        arena.run_arena_tick()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"arena tick failed: {e}") from e
    return arena.get_arena()


@router.post("/reset", response_model=arena.ArenaOut)
def reset() -> arena.ArenaOut:
    return arena.reset_arena()
