"""Watchlist CRUD + CSV import routes."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from lucore.services import watchlist as wl
from lucore.services.futu_import import (
    EbkExport,
    EbkImportResult,
    export_watchlist_ebk,
    import_ebk_files,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class CreateWatchlist(BaseModel):
    name: str
    description: str | None = None


class EbkFile(BaseModel):
    name: str
    content: str


class AddItem(BaseModel):
    symbol: str
    tags: str | None = None
    note: str | None = None


class UpdateWatchlist(BaseModel):
    name: str
    description: str | None = None


class UpdateItem(BaseModel):
    tags: str | None = None
    note: str | None = None


class ReorderIds(BaseModel):
    ordered_ids: list[int]


class ReorderItems(BaseModel):
    ordered_item_ids: list[int]


class MoveItem(BaseModel):
    watchlist_id: int


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


@router.post("/reorder")
def reorder_groups(body: ReorderIds) -> dict:
    """Persist the display order of watchlist groups."""
    return {"ok": wl.reorder_watchlists(body.ordered_ids)}


@router.patch("/items/{item_id}", response_model=wl.WatchlistItemOut)
def update_item(item_id: int, body: UpdateItem) -> wl.WatchlistItemOut:
    """Edit an item's tags/note (tags = comma-separated, order preserved)."""
    item = wl.update_item(item_id, tags=body.tags, note=body.note)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


@router.post("/items/{item_id}/move")
def move_item(item_id: int, body: MoveItem) -> dict:
    """Move an item into another group (merges if the symbol already exists there)."""
    return {"ok": wl.move_item(item_id, body.watchlist_id)}


@router.get("/{watchlist_id}", response_model=wl.WatchlistOut)
def get_one(watchlist_id: int) -> wl.WatchlistOut:
    got = wl.get_watchlist(watchlist_id)
    if got is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return got


@router.patch("/{watchlist_id}", response_model=wl.WatchlistOut)
def rename(watchlist_id: int, body: UpdateWatchlist) -> wl.WatchlistOut:
    got = wl.rename_watchlist(watchlist_id, body.name, body.description)
    if got is None:
        raise HTTPException(status_code=404, detail="watchlist not found or empty name")
    return got


@router.delete("/{watchlist_id}")
def delete_group(watchlist_id: int) -> dict:
    return {"removed": wl.delete_watchlist(watchlist_id)}


@router.post("/{watchlist_id}/reorder-items")
def reorder_items(watchlist_id: int, body: ReorderItems) -> dict:
    """Persist within-group item order."""
    return {"ok": wl.reorder_items(watchlist_id, body.ordered_item_ids)}


@router.post("/{watchlist_id}/items", response_model=wl.WatchlistItemOut)
def add(watchlist_id: int, body: AddItem) -> wl.WatchlistItemOut:
    item = wl.add_item(watchlist_id, body.symbol, body.tags, body.note)
    if item is None:
        raise HTTPException(status_code=400, detail="invalid symbol")
    return item


@router.delete("/items/{item_id}")
def remove(item_id: int) -> dict:
    return {"removed": wl.remove_item(item_id)}


@router.get("/{watchlist_id}/quotes", response_model=list[wl.QuoteRow])
def quotes(watchlist_id: int) -> list[wl.QuoteRow]:
    """Dense quote rows (price + change + sparkline) read from stored snapshots (fast)."""
    return wl.quotes_for(watchlist_id)


@router.post("/{watchlist_id}/import-csv")
def import_csv(watchlist_id: int, csv_text: str = Body(..., media_type="text/plain")) -> dict:
    return {"added": wl.import_csv(watchlist_id, csv_text)}


@router.post("/import-ebk", response_model=EbkImportResult)
def import_ebk(files: list[EbkFile]) -> EbkImportResult:
    """Import Futu .ebk exports — one LU watchlist per file (filename = group name)."""
    return import_ebk_files([f.model_dump() for f in files])


@router.get("/{watchlist_id}/export-ebk", response_model=EbkExport)
def export_ebk(watchlist_id: int) -> EbkExport:
    """Export a group as Futu .ebk text (re-importable by Futu)."""
    out = export_watchlist_ebk(watchlist_id)
    if out is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return out
