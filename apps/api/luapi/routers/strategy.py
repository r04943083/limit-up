"""Strategy builder + backtest routes (#9)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.compute.backtest import STRATEGIES, BacktestResult, StrategySpec
from lucore.services import strategy as strat

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/kinds")
def kinds() -> list[str]:
    return STRATEGIES


@router.post("/backtest", response_model=BacktestResult)
def run(symbol: str, spec: StrategySpec, period: str = "3y") -> BacktestResult:
    try:
        return strat.run_backtest(symbol, spec, period=period)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"backtest failed: {e}") from e


@router.post("/explain", response_model=strat.StrategyRead)
def explain(symbol: str, spec: StrategySpec, period: str = "3y") -> strat.StrategyRead:
    try:
        result = strat.run_backtest(symbol, spec, period=period)
        return strat.explain(result)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"explain failed: {e}") from e
