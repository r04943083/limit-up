"""Portfolio routes: holdings CRUD + CSV import, analytics, AI review."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from lucore.compute.portfolio import PortfolioAnalytics
from lucore.services import portfolio as pf
from lucore.services.portfolio_perf import PortfolioTearsheet, compute_portfolio_tearsheet

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class HoldingIn(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float | None = None


@router.get("/default")
def default() -> dict:
    pid = pf.ensure_default_portfolio()
    return {"id": pid, "holdings": pf.list_holdings(pid)}


@router.post("/{portfolio_id}/holdings")
def add_holding(portfolio_id: int, body: HoldingIn) -> dict:
    pf.upsert_holding(portfolio_id, body.symbol, body.quantity, body.avg_cost, source="manual")
    return {"holdings": pf.list_holdings(portfolio_id)}


@router.delete("/holdings/{holding_id}")
def remove_holding(holding_id: int) -> dict:
    return {"removed": pf.remove_holding(holding_id)}


@router.post("/{portfolio_id}/import-csv")
def import_csv(portfolio_id: int, csv_text: str = Body(..., media_type="text/plain")) -> dict:
    return {"added": pf.import_csv(portfolio_id, csv_text)}


@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalytics)
def analytics(portfolio_id: int) -> PortfolioAnalytics:
    try:
        return pf.get_analytics(portfolio_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"analytics error: {e}") from e


@router.get("/{portfolio_id}/tearsheet", response_model=PortfolioTearsheet)
def tearsheet(portfolio_id: int) -> PortfolioTearsheet:
    """Rigorous risk/return tear-sheet (Sharpe/Sortino/Calmar, drawdown, VaR/CVaR, monthly
    returns, vs-SPY alpha/beta) over the current basket's ~1y reconstructed equity curve."""
    try:
        return compute_portfolio_tearsheet(portfolio_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"tearsheet error: {e}") from e


@router.post("/{portfolio_id}/review")
def review(portfolio_id: int) -> dict:
    try:
        return pf.review_portfolio(portfolio_id).model_dump()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"review failed: {e}") from e


@router.get("/{portfolio_id}/review")
def get_review(portfolio_id: int) -> dict | None:
    r = pf.latest_review(portfolio_id)
    return r.model_dump() if r else None
