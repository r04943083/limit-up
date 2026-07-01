"""AI 涨停复盘 (limit-up review): deterministic facts from the day's limit-up pool +
dragon-tiger + HSGT → claude -p writes a Chinese 复盘 narrative.

Facts (counts, tiers, leaders, industries, capital) are computed here; the LLM only
narrates over them — never invents names or numbers. Cached per date in
``market_data_cache`` (key ``ztreview:<date>``); regenerate via ``compute_zt_review(force=True)``.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter

from pydantic import BaseModel

from ..db import session_scope
from ..db.models import MarketDataCache
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage
from .cn_market import get_dragon_tiger, get_hsgt_summary, get_limit_up_pool

SYSTEM_PROMPT = (
    "You are LU's A-share end-of-day 涨停复盘 (limit-up review) analyst for a personal investor. "
    "You are given deterministic FACTS computed by LU: limit-up count, the 连板 ladder (how many "
    "names at each consecutive-board height), the day's 龙头 (highest boards), leading industries, "
    "dragon-tiger net buying, and 沪深港通 southbound flow. Reason ONLY over these facts — never "
    "invent stock names, prices, or numbers. Judge market 情绪 (sentiment/温度), ladder health "
    "(是否有高度、断板与否、梯队是否完整), the dominant 主线/方向, the capital backdrop, and the "
    "retreat/risk signals. Respond with ONLY one JSON object."
)

OUTPUT_SPEC = {
    "sentiment": "one short line on market 情绪/温度 (e.g. '情绪偏暖,高度板回封,梯队完整')",
    "summary": "2-4 sentences overall 复盘 of the limit-up landscape",
    "ladder_read": "1-3 sentences reading the 连板梯队 (height, 晋级/断板, completeness)",
    "leaders": ["bullets: dominant 主线/方向 and the names anchoring them (from facts)"],
    "capital": "1-2 sentences on the capital backdrop (龙虎榜 net buying, 南向资金)",
    "risks": ["bullets: 退潮/风险 signals to watch tomorrow"],
}

_YI = 1e8


class ZtReviewResult(BaseModel):
    sentiment: str = ""
    summary: str = ""
    ladder_read: str = ""
    leaders: list[str] = []
    capital: str = ""
    risks: list[str] = []


class SavedZtReview(BaseModel):
    date: str
    provider: str
    created_at: dt.datetime
    result: ZtReviewResult
    facts: dict = {}


def _today() -> str:
    return dt.date.today().strftime("%Y%m%d")


def _yi(v: float | None) -> float | None:
    return round(v / _YI, 2) if v is not None else None


def gather_facts(date: str) -> dict:
    lu = get_limit_up_pool(date)
    pool = lu.pool
    lhb = get_dragon_tiger(date).data
    hsgt = get_hsgt_summary().summary

    tiers: Counter[int] = Counter()
    industries: Counter[str] = Counter()
    for s in pool.stocks:
        tiers[s.boards or 1] += 1
        if s.industry:
            industries[s.industry] += 1
    max_boards = max(tiers) if tiers else 0
    leaders = [s.name for s in pool.stocks if (s.boards or 1) == max_boards and max_boards >= 2]

    big_seal = sorted(pool.stocks, key=lambda s: s.seal_fund or 0, reverse=True)[:5]
    lhb_top = sorted(lhb.rows, key=lambda r: r.net_buy or 0, reverse=True)[:5]
    south_net = sum((r.net or 0) for r in hsgt.rows if r.direction == "南向")

    return {
        "date": date,
        "_pool_ok": lu.ok,
        "zt_count": pool.count,
        "ladder": {f"{b}连板" if b >= 2 else "首板": n for b, n in sorted(tiers.items(), reverse=True)},
        "max_boards": max_boards,
        "leaders": leaders[:8],
        "top_industries": [{"industry": k, "count": v} for k, v in industries.most_common(6)],
        "biggest_seal_fund": [{"name": s.name, "seal_fund_yi": _yi(s.seal_fund), "boards": s.boards} for s in big_seal],
        "dragon_tiger_count": lhb.count,
        "dragon_tiger_top_net_buy": [{"name": r.name, "net_buy_yi": _yi(r.net_buy), "reason": r.reason} for r in lhb_top],
        "hsgt_southbound_net_yi": round(south_net, 2),
        "northbound_suspended": hsgt.northbound_suspended,
    }


def _key(date: str) -> str:
    return f"ztreview:{date}"


def _read(date: str) -> SavedZtReview | None:
    with session_scope() as s:
        row = s.get(MarketDataCache, _key(date))
        if row is None:
            return None
        try:
            return SavedZtReview.model_validate_json(row.payload_json)
        except Exception:  # noqa: BLE001
            return None


def latest_zt_review(date: str | None = None) -> SavedZtReview | None:
    return _read(date or _today())


def compute_zt_review(
    date: str | None = None, *, force: bool = False, provider: LLMProvider | None = None
) -> SavedZtReview:
    date = date or _today()
    if not force:
        cached = _read(date)
        if cached is not None:
            return cached

    facts = gather_facts(date)
    pool_ok = facts.pop("_pool_ok", True)
    provider = provider or get_provider()

    if facts["zt_count"] == 0:
        result = ZtReviewResult(
            sentiment="该日无涨停数据",
            summary="该日无涨停股(可能为非交易日或数据源尚未更新)。",
        )
        # A *failed* limit-up fetch also yields count==0. Never persist that — it would
        # poison the day's review cache and be served forever. Return an ephemeral result
        # so the next call (once akshare recovers) recomputes from real data.
        if not pool_ok:
            return SavedZtReview(
                date=date, provider="cache-miss",
                created_at=dt.datetime.now(dt.timezone.utc), result=result, facts=facts,
            )
    else:
        prompt = (
            "Write today's 涨停复盘. FACTS (ground truth):\n"
            f"{json.dumps(facts, indent=2, ensure_ascii=False, default=str)}\n\n"
            f"Return ONLY JSON with exactly these keys:\n{json.dumps(OUTPUT_SPEC, indent=2, ensure_ascii=False)}"
        )
        raw = provider.generate_json(prompt, system=with_chinese(SYSTEM_PROMPT))
        usage.record(provider, "zt_review", None)
        result = ZtReviewResult.model_validate(raw)

    saved = SavedZtReview(
        date=date, provider=provider.name,
        created_at=dt.datetime.now(dt.timezone.utc), result=result, facts=facts,
    )
    with session_scope() as s:
        row = s.get(MarketDataCache, _key(date))
        payload = saved.model_dump_json()
        if row is None:
            s.add(MarketDataCache(cache_key=_key(date), payload_json=payload,
                                  fetched_at=dt.datetime.now(dt.timezone.utc)))
        else:
            row.payload_json = payload
            row.fetched_at = dt.datetime.now(dt.timezone.utc)
    return saved
