"""Shared cache-first plumbing for *market-level* feeds (A-share limit-up / dragon-tiger /
HSGT, US movers, …). These feeds are market-wide, not per-symbol, so they live outside the
per-symbol DataRouter/Snapshot path and share this key→JSON store (``market_data_cache``).

Policy: a **past** trading day is immutable (cache forever); **today** refreshes intra-day
after ``today_ttl_min`` minutes. This is the one place that logic lives so every feed —
regardless of market — behaves identically.
"""
from __future__ import annotations

import datetime as dt

from ..db import session_scope
from ..db.models import MarketDataCache

DEFAULT_TODAY_TTL_MIN = 30


def aware(d: dt.datetime) -> dt.datetime:
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def today_str() -> str:
    return dt.date.today().strftime("%Y%m%d")


def read(key: str) -> tuple[str | None, dt.datetime | None]:
    with session_scope() as s:
        row = s.get(MarketDataCache, key)
        if row is None:
            return None, None
        return row.payload_json, row.fetched_at


def write(key: str, payload: str) -> None:
    with session_scope() as s:
        row = s.get(MarketDataCache, key)
        now = dt.datetime.now(dt.timezone.utc)
        if row is None:
            s.add(MarketDataCache(cache_key=key, payload_json=payload, fetched_at=now))
        else:
            row.payload_json = payload
            row.fetched_at = now


def fresh_enough(
    fetched_at: dt.datetime | None, *, is_today: bool, today_ttl_min: int = DEFAULT_TODAY_TTL_MIN
) -> bool:
    if fetched_at is None:
        return False
    if not is_today:
        return True  # past days are immutable
    age = dt.datetime.now(dt.timezone.utc) - aware(fetched_at)
    return age.total_seconds() < today_ttl_min * 60
