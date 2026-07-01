"""Cache-first A-share breadth feeds (limit-up pool / dragon-tiger / HSGT summary).

Caching policy via ``market_data_cache``:
- A **past** trading day is immutable → once cached, never refetch.
- **Today** refreshes intra-day (≥ _TODAY_TTL_MIN minutes stale).
- HSGT summary always uses the today policy.

akshare can fail (network / rate-limit / schema drift); callers get whatever last
succeeded from cache, or an empty result with ``ok=False`` on a cold failure.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..data import cn_market as cn
from . import market_cache as mc

_TODAY_TTL_MIN = 30


def _today_str() -> str:
    return mc.today_str()


def _read(key: str) -> tuple[str | None, "object | None"]:
    return mc.read(key)


def _write(key: str, payload: str) -> None:
    mc.write(key, payload)


def _fresh_enough(key: str, fetched_at, *, is_today: bool) -> bool:  # noqa: ANN001
    return mc.fresh_enough(fetched_at, is_today=is_today, today_ttl_min=_TODAY_TTL_MIN)


class LimitUpResult(BaseModel):
    ok: bool = True
    error: str | None = None
    pool: cn.LimitUpPool


class DragonTigerResult(BaseModel):
    ok: bool = True
    error: str | None = None
    data: cn.DragonTiger


class HsgtResult(BaseModel):
    ok: bool = True
    error: str | None = None
    summary: cn.HsgtSummary


def get_limit_up_pool(date: str | None = None) -> LimitUpResult:
    date = date or _today_str()
    key = f"ztpool:{date}"
    is_today = date == _today_str()
    cached, fetched = _read(key)
    if cached and _fresh_enough(key, fetched, is_today=is_today):
        return LimitUpResult(pool=cn.LimitUpPool.model_validate_json(cached))
    try:
        pool = cn.fetch_limit_up_pool(date)
        _write(key, pool.model_dump_json())
        return LimitUpResult(pool=pool)
    except Exception as e:  # noqa: BLE001
        if cached:
            return LimitUpResult(ok=False, error=str(e), pool=cn.LimitUpPool.model_validate_json(cached))
        return LimitUpResult(ok=False, error=str(e), pool=cn.LimitUpPool(date=date))


def get_dragon_tiger(date: str | None = None) -> DragonTigerResult:
    date = date or _today_str()
    key = f"lhb:{date}"
    is_today = date == _today_str()
    cached, fetched = _read(key)
    if cached and _fresh_enough(key, fetched, is_today=is_today):
        return DragonTigerResult(data=cn.DragonTiger.model_validate_json(cached))
    try:
        data = cn.fetch_dragon_tiger(date)
        _write(key, data.model_dump_json())
        return DragonTigerResult(data=data)
    except Exception as e:  # noqa: BLE001
        if cached:
            return DragonTigerResult(ok=False, error=str(e), data=cn.DragonTiger.model_validate_json(cached))
        return DragonTigerResult(ok=False, error=str(e), data=cn.DragonTiger(date=date))


def get_hsgt_summary() -> HsgtResult:
    key = "hsgt:summary"
    cached, fetched = _read(key)
    if cached and _fresh_enough(key, fetched, is_today=True):
        return HsgtResult(summary=cn.HsgtSummary.model_validate_json(cached))
    try:
        summary = cn.fetch_hsgt_summary()
        _write(key, summary.model_dump_json())
        return HsgtResult(summary=summary)
    except Exception as e:  # noqa: BLE001
        if cached:
            return HsgtResult(ok=False, error=str(e), summary=cn.HsgtSummary.model_validate_json(cached))
        return HsgtResult(ok=False, error=str(e), summary=cn.HsgtSummary())
