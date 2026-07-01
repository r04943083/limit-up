"""Cache-first US market-breadth feeds (Yahoo movers) — the US analogue of cn_market.

Movers change intra-day, so every board uses the "today" TTL policy (refresh after a few
minutes stale). On a cold failure the caller gets an empty board with ``ok=False``; if a
prior good board is cached it is served instead so the 发现 page never goes blank.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..data import us_market as us
from . import market_cache as mc

_TTL_MIN = 10  # movers are intra-day; keep them reasonably fresh


class MoversResult(BaseModel):
    ok: bool = True
    error: str | None = None
    board: us.MoversBoard


class Feed(BaseModel):
    kind: str
    label: str


def list_feeds() -> list[Feed]:
    """The US discovery feeds available (kind + Chinese label), in display order."""
    return [Feed(kind=k, label=v) for k, v in us.US_FEEDS.items()]


def get_movers(kind: str, count: int = 30, *, allow_fetch: bool = True) -> MoversResult:
    """Cache-first US movers board.

    ``allow_fetch=False`` makes this a pure cache read (no network): it returns the cached
    board if present — even if stale — else an empty ``ok=False`` result. Used by the daily
    briefing so assembling facts never blocks on live Yahoo fetches.
    """
    count = max(1, min(count, 250))  # yf.screen rejects count > 250
    key = f"us_movers:{kind}:{count}:{mc.today_str()}"
    cached, fetched = mc.read(key)
    if cached and mc.fresh_enough(fetched, is_today=True, today_ttl_min=_TTL_MIN):
        return MoversResult(board=us.MoversBoard.model_validate_json(cached))
    label = us.US_FEEDS.get(kind, kind)
    if not allow_fetch:
        if cached:  # serve stale cache rather than hit the network
            return MoversResult(board=us.MoversBoard.model_validate_json(cached))
        return MoversResult(ok=False, error="no cached data",
                            board=us.MoversBoard(kind=kind, label=label))
    try:
        board = us.fetch_movers(kind, count=count)
        mc.write(key, board.model_dump_json())
        return MoversResult(board=board)
    except Exception as e:  # noqa: BLE001
        if cached:
            return MoversResult(ok=False, error=str(e),
                                board=us.MoversBoard.model_validate_json(cached))
        return MoversResult(ok=False, error=str(e),
                            board=us.MoversBoard(kind=kind, label=label))
