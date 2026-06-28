"""A-share market-breadth routes (limit-up pool / dragon-tiger / HSGT), via akshare.

Cache-first in lucore.services.cn_market; data is market-wide, not per-symbol.
"""
from __future__ import annotations

from fastapi import APIRouter

from fastapi import HTTPException

from lucore.services.cn_market import (
    DragonTigerResult,
    HsgtResult,
    LimitUpResult,
    get_dragon_tiger,
    get_hsgt_summary,
    get_limit_up_pool,
)
from lucore.services.cn_review import SavedZtReview, compute_zt_review, latest_zt_review

router = APIRouter(prefix="/cn", tags=["cn"])


@router.get("/limit-up", response_model=LimitUpResult)
def limit_up(date: str | None = None) -> LimitUpResult:
    """涨停股池 (东方财富). date='YYYYMMDD', omit for today. Cache-first."""
    return get_limit_up_pool(date)


@router.get("/dragon-tiger", response_model=DragonTigerResult)
def dragon_tiger(date: str | None = None) -> DragonTigerResult:
    """龙虎榜明细. date='YYYYMMDD', omit for today. Cache-first."""
    return get_dragon_tiger(date)


@router.get("/hsgt-summary", response_model=HsgtResult)
def hsgt_summary() -> HsgtResult:
    """沪深港通资金流向汇总(北向实时净额已停发,南向仍有数据)。"""
    return get_hsgt_summary()


@router.get("/review", response_model=SavedZtReview | None)
def review(date: str | None = None) -> SavedZtReview | None:
    """已生成的 AI 涨停复盘(无则返回 null)。date='YYYYMMDD',省略为今日。"""
    return latest_zt_review(date)


@router.post("/review", response_model=SavedZtReview)
def run_review(date: str | None = None, force: bool = False) -> SavedZtReview:
    """生成 AI 涨停复盘(claude -p)。同步,约 20–40 秒。"""
    try:
        return compute_zt_review(date, force=force)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"review failed: {e}") from e
