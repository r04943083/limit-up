"""Investment journal routes (#11)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lucore.services import journal as jr

router = APIRouter(prefix="/journal", tags=["journal"])


class CreateEntry(BaseModel):
    title: str
    body: str | None = None
    symbol: str | None = None
    action: str = "note"
    conviction: str | None = None


@router.get("", response_model=list[jr.JournalOut])
def list_entries(symbol: str | None = None) -> list[jr.JournalOut]:
    return jr.list_entries(symbol)


@router.post("", response_model=jr.JournalOut)
def add_entry(body: CreateEntry) -> jr.JournalOut:
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="title required")
    return jr.add_entry(
        title=body.title, body=body.body, symbol=body.symbol,
        action=body.action, conviction=body.conviction,
    )


@router.delete("/{entry_id}")
def delete_entry(entry_id: int) -> dict:
    return {"removed": jr.delete_entry(entry_id)}


@router.post("/{entry_id}/review", response_model=jr.JournalOut)
def review_entry(entry_id: int) -> jr.JournalOut:
    try:
        out = jr.review_entry(entry_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"review failed: {e}") from e
    if out is None:
        raise HTTPException(status_code=404, detail="entry not found")
    return out
