"""Industry-average valuation (行业平均 PE / PB / PS).

Futu shows each stock's PE/PB/PS next to its industry average. yfinance has no such field,
so we *compute* it deterministically: the median PE/PB/PS across the peers in the same
industry that we've already downloaded (their cached snapshots). The whole industry→median
map is built in one pass over snapshots and cached for a day (it shifts slowly), so the
per-stock 分析 panel stays instant. Honest about coverage: industries with <3 priced peers
return None rather than a misleading number.
"""
from __future__ import annotations

import datetime as dt
import json
import statistics

from pydantic import BaseModel
from sqlalchemy import select

from ..db import session_scope
from ..db.models import MarketDataCache, Snapshot, Stock

_CACHE_KEY = "industry_medians:v1"
_TTL_HOURS = 24
_MIN_PEERS = 3  # below this an "average" is noise, not signal


class IndustryMedian(BaseModel):
    industry: str
    n: int = 0
    pe: float | None = None
    pb: float | None = None
    ps: float | None = None


def _positive(values: list[float | None]) -> list[float]:
    return [v for v in values if v is not None and v > 0]


def _compute_medians() -> dict[str, IndustryMedian]:
    """One pass over snapshots: group cached PE/PB/PS by the stock's industry, take medians."""
    by_industry: dict[str, dict[str, list[float | None]]] = {}
    with session_scope() as s:
        rows = s.execute(
            select(Stock.industry, Snapshot.bundle_json)
            .join(Stock, Stock.symbol == Snapshot.symbol)
            .where(Stock.industry.isnot(None))
        ).all()
    for industry, bundle_json in rows:
        if not industry or not bundle_json:
            continue
        try:
            fund = json.loads(bundle_json).get("fundamentals") or {}
        except (ValueError, AttributeError):
            continue
        bucket = by_industry.setdefault(industry, {"pe": [], "pb": [], "ps": []})
        bucket["pe"].append(fund.get("pe_ttm"))
        bucket["pb"].append(fund.get("pb"))
        bucket["ps"].append(fund.get("ps"))

    out: dict[str, IndustryMedian] = {}
    for industry, b in by_industry.items():
        pe, pb, ps = _positive(b["pe"]), _positive(b["pb"]), _positive(b["ps"])
        n = max(len(pe), len(pb), len(ps))
        out[industry] = IndustryMedian(
            industry=industry, n=n,
            pe=statistics.median(pe) if len(pe) >= _MIN_PEERS else None,
            pb=statistics.median(pb) if len(pb) >= _MIN_PEERS else None,
            ps=statistics.median(ps) if len(ps) >= _MIN_PEERS else None,
        )
    return out


def _aware(d: dt.datetime) -> dt.datetime:
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def industry_medians(force: bool = False) -> dict[str, IndustryMedian]:
    """Cached map {industry: IndustryMedian}. Recomputed at most once per day."""
    now = dt.datetime.now(dt.timezone.utc)
    with session_scope() as s:
        row = s.get(MarketDataCache, _CACHE_KEY)
        if row and not force and (now - _aware(row.fetched_at)).total_seconds() < _TTL_HOURS * 3600:
            try:
                cached = json.loads(row.payload_json)
                return {k: IndustryMedian(**v) for k, v in cached.items()}
            except (ValueError, TypeError):
                pass

    medians = _compute_medians()
    payload = json.dumps({k: v.model_dump() for k, v in medians.items()})
    with session_scope() as s:
        row = s.get(MarketDataCache, _CACHE_KEY)
        if row is None:
            s.add(MarketDataCache(cache_key=_CACHE_KEY, payload_json=payload, fetched_at=now))
        else:
            row.payload_json = payload
            row.fetched_at = now
    return medians


def industry_average(symbol: str) -> IndustryMedian | None:
    """Median PE/PB/PS for `symbol`'s industry (None if industry unknown / too few peers)."""
    with session_scope() as s:
        stock = s.get(Stock, symbol.upper())
        industry = stock.industry if stock else None
    if not industry:
        return None
    return industry_medians().get(industry)
