"""Symbol search — resolve a free-text query to real symbols we've downloaded.

The global search box must never navigate to a made-up ticker (typing "tesla" used to
jump to /research/TESLA and 500). This searches the local `stocks` universe by ticker
*and* name (Chinese or English), ranked so the best match is first, so the UI can show
an autocomplete dropdown and only ever open a symbol that actually exists.
"""
from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select

from ..db import session_scope
from ..db.models import Stock


class SymbolHit(BaseModel):
    symbol: str
    name: str | None = None
    market: str | None = None


def _rank(q: str, sym: str, name: str | None) -> int:
    """Lower = better. Exact ticker → ticker prefix → name prefix → ticker/name contains."""
    s = sym.upper()
    n = (name or "").upper()
    if s == q:
        return 0
    if s.startswith(q):
        return 1
    if n.startswith(q):
        return 2
    if q in s:
        return 3
    return 4


def search_symbols(query: str, limit: int = 20) -> list[SymbolHit]:
    """Return the best symbol matches for `query` across ticker + name (case-insensitive).

    Empty query → empty list. Matches our downloaded universe only, so every hit is a
    symbol the rest of the app can actually render."""
    q = (query or "").strip().upper()
    if not q:
        return []
    like = f"%{q}%"
    with session_scope() as s:
        rows = s.execute(
            select(Stock.symbol, Stock.name, Stock.market).where(
                Stock.name.isnot(None),  # skip half-synced junk rows (no name = no usable data)
                (Stock.symbol.ilike(like)) | (Stock.name.ilike(like)),
            )
        ).all()
    hits = [SymbolHit(symbol=r[0], name=r[1], market=r[2]) for r in rows]
    hits.sort(key=lambda h: (_rank(q, h.symbol, h.name), len(h.symbol), h.symbol))
    return hits[:limit]
