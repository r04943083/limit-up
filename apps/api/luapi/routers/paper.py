"""Paper trading routes (#8)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lucore.services import paper

router = APIRouter(prefix="/paper", tags=["paper"])


class TradeIn(BaseModel):
    symbol: str
    side: str  # buy | sell
    quantity: float
    note: str | None = None


@router.get("/account", response_model=paper.PaperAccountOut)
def account() -> paper.PaperAccountOut:
    return paper.get_account()


@router.post("/trade", response_model=paper.PaperAccountOut)
def trade(body: TradeIn) -> paper.PaperAccountOut:
    try:
        return paper.trade(body.symbol, body.side, body.quantity, note=body.note)
    except paper.TradeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"trade failed: {e}") from e


@router.post("/reset", response_model=paper.PaperAccountOut)
def reset() -> paper.PaperAccountOut:
    return paper.reset()
