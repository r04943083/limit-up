"""Company profile service: cache-first overview + dividends + ownership.

Profiles change slowly, so they're cached in ``profile_cache`` and refreshed
lazily (≥7 days stale) — same pattern as the financials service.
"""
from __future__ import annotations

import datetime as dt

from ..data.base import CompanyProfile
from ..data.router import get_router
from ..db import session_scope
from ..db.models import ProfileCache

_STALE_DAYS = 7


def _aware(d: dt.datetime) -> dt.datetime:
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def get_profile_cached(symbol: str, refresh: bool = True) -> CompanyProfile:
    sym = symbol.strip().upper()
    with session_scope() as s:
        row = s.get(ProfileCache, sym)
        fresh = False
        if row is not None and row.fetched_at is not None:
            age = dt.datetime.now(dt.timezone.utc) - _aware(row.fetched_at)
            fresh = age.days < _STALE_DAYS
        if row is not None and (fresh or not refresh):
            try:
                return CompanyProfile.model_validate_json(row.payload_json)
            except Exception:  # noqa: BLE001 - corrupt cache -> refetch below
                pass

    prof = get_router().get_profile(sym)
    payload = prof.model_dump_json()
    with session_scope() as s:
        row = s.get(ProfileCache, sym)
        if row is None:
            s.add(ProfileCache(symbol=sym, payload_json=payload,
                               fetched_at=dt.datetime.now(dt.timezone.utc)))
        else:
            row.payload_json = payload
            row.fetched_at = dt.datetime.now(dt.timezone.utc)
    return prof
