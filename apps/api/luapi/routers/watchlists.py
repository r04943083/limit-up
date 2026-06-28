"""Watchlist CRUD + CSV import routes."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from lucore.services import watchlist as wl

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class CreateWatchlist(BaseModel):
    name: str
    description: str | None = None


class AddItem(BaseModel):
    symbol: str
    tags: str | None = None
    note: str | None = None


@router.get("", response_model=list[wl.WatchlistOut])
def list_all() -> list[wl.WatchlistOut]:
    return wl.list_watchlists()


@router.get("/default", response_model=wl.WatchlistOut)
def default() -> wl.WatchlistOut:
    wid = wl.ensure_default_watchlist()
    got = wl.get_watchlist(wid)
    assert got is not None
    return got


@router.post("", response_model=wl.WatchlistOut)
def create(body: CreateWatchlist) -> wl.WatchlistOut:
    return wl.create_watchlist(body.name, body.description)


@router.get("/{watchlist_id}", response_model=wl.WatchlistOut)
def get_one(watchlist_id: int) -> wl.WatchlistOut:
    got = wl.get_watchlist(watchlist_id)
    if got is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return got


@router.post("/{watchlist_id}/items", response_model=wl.WatchlistItemOut)
def add(watchlist_id: int, body: AddItem) -> wl.WatchlistItemOut:
    item = wl.add_item(watchlist_id, body.symbol, body.tags, body.note)
    if item is None:
        raise HTTPException(status_code=400, detail="invalid symbol")
    return item


@router.delete("/items/{item_id}")
def remove(item_id: int) -> dict:
    return {"removed": wl.remove_item(item_id)}


@router.post("/{watchlist_id}/import-csv")
def import_csv(watchlist_id: int, csv_text: str = Body(..., media_type="text/plain")) -> dict:
    return {"added": wl.import_csv(watchlist_id, csv_text)}
