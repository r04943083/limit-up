"""Daily briefing (#D5) + opportunity surfacing (#D2) + watchlist health (#D3).

Deterministic assembly from cached snapshots (fast, no live fetches) → claude -p writes
the narrative. One briefing per day (idempotent). Also persists per-item health scores.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel
from sqlalchemy import select

from ..compute.health import health_score
from ..db import session_scope
from ..db.models import Briefing, Recommendation, WatchlistItem
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage
from .research import load_snapshot
from .sync import tracked_symbols

SYSTEM_PROMPT = (
    "You are LU's morning market briefer for a personal investor. You are given deterministic "
    "FACTS computed by LU (watchlist movers, health scores, recent recommendations, news tone). "
    "Write a crisp, scannable daily briefing. Reason only over the facts — never invent prices, "
    "events, or numbers. Respond with ONLY one JSON object."
)

OUTPUT_SPEC = {
    "headline": "one punchy sentence capturing the day's setup for this watchlist",
    "market_summary": "2-4 sentences on the overall posture across the tracked names",
    "watchlist_highlights": ["bullets on notable movers / signals worth attention"],
    "opportunities": ["bullets: names/setups that look interesting and why (from the facts)"],
    "risks": ["bullets: what to watch out for / weakening names"],
    "action_items": ["short, concrete suggestions (e.g. 'review NVDA — overbought')"],
}


class BriefingResult(BaseModel):
    headline: str = ""
    market_summary: str = ""
    watchlist_highlights: list[str] = []
    opportunities: list[str] = []
    risks: list[str] = []
    action_items: list[str] = []


class SavedBriefing(BaseModel):
    date: str
    provider: str
    created_at: dt.datetime
    result: BriefingResult
    facts: dict = {}


class HealthOut(BaseModel):
    symbol: str
    score: float
    label: str
    factors: list[str] = []


def compute_watchlist_health() -> list[HealthOut]:
    """Compute health for every watchlist item from its snapshot, persist score on the item."""
    out: list[HealthOut] = []
    with session_scope() as s:
        items = s.execute(select(WatchlistItem)).scalars().all()
        for it in items:
            snap = load_snapshot(it.symbol)
            if snap is None:
                continue
            tl = snap.technical_latest
            f = snap.fundamentals
            h = health_score(
                price=tl.get("price"), sma50=tl.get("sma50"), sma200=tl.get("sma200"),
                rsi=tl.get("rsi14"), trend=snap.technical_trend,
                week52_low=f.week52_low, week52_high=f.week52_high,
            )
            it.health_score = h.score
            out.append(HealthOut(symbol=it.symbol, score=h.score, label=h.label, factors=h.factors))
    out.sort(key=lambda x: -x.score)
    return out


def _gather_facts() -> dict:
    """Assemble briefing facts purely from cached snapshots (fast)."""
    movers = []
    for sym in tracked_symbols():
        snap = load_snapshot(sym)
        if snap is None:
            continue
        tl = snap.technical_latest
        f = snap.fundamentals
        h = health_score(
            price=tl.get("price"), sma50=tl.get("sma50"), sma200=tl.get("sma200"),
            rsi=tl.get("rsi14"), trend=snap.technical_trend,
            week52_low=f.week52_low, week52_high=f.week52_high,
        )
        movers.append({
            "symbol": sym, "name": f.name, "price": snap.quote.price,
            "change_pct": snap.quote.change_pct, "trend": snap.technical_trend,
            "rsi": tl.get("rsi14"), "signals": snap.technical_signals[:3],
            "health": h.score, "health_label": h.label,
        })
    movers.sort(key=lambda m: (m["change_pct"] if m["change_pct"] is not None else 0), reverse=True)

    with session_scope() as s:
        recos = s.execute(
            select(Recommendation).order_by(Recommendation.ai_score.desc().nullslast()).limit(5)
        ).scalars().all()
        top_recos = [
            {"symbol": r.symbol, "category": r.category, "ai_score": r.ai_score, "conviction": r.conviction}
            for r in recos
        ]

    gainers = [m for m in movers if (m["change_pct"] or 0) > 0][:5]
    losers = [m for m in movers if (m["change_pct"] or 0) < 0][-5:]
    weakest = sorted(movers, key=lambda m: m["health"])[:3]
    strongest = sorted(movers, key=lambda m: -m["health"])[:3]
    return {
        "date": dt.date.today().isoformat(),
        "tracked_count": len(movers),
        "top_gainers": gainers,
        "top_losers": losers,
        "strongest_health": strongest,
        "weakest_health": weakest,
        "top_recommendations": top_recos,
    }


def generate_briefing(*, provider: LLMProvider | None = None) -> SavedBriefing:
    compute_watchlist_health()
    facts = _gather_facts()
    provider = provider or get_provider()

    if facts["tracked_count"] == 0:
        result = BriefingResult(
            headline="暂无跟踪标的",
            market_summary="自选列表和组合都为空。添加一些标的并点击“全部更新”后即可生成每日简报。",
        )
    else:
        prompt = (
            "Write today's briefing. FACTS (ground truth):\n"
            f"{json.dumps(facts, indent=2, ensure_ascii=False, default=str)}\n\n"
            f"Return ONLY JSON with exactly these keys:\n{json.dumps(OUTPUT_SPEC, indent=2)}"
        )
        raw = provider.generate_json(prompt, system=with_chinese(SYSTEM_PROMPT))
        usage.record(provider, "briefing", None)
        result = BriefingResult.model_validate(raw)

    return _persist(result, facts, provider.name)


def _persist(result: BriefingResult, facts: dict, provider: str) -> SavedBriefing:
    today = dt.date.today().isoformat()
    with session_scope() as s:
        row = s.execute(select(Briefing).where(Briefing.date == today)).scalar_one_or_none()
        if row is None:
            row = Briefing(date=today)
            s.add(row)
        row.summary = result.headline
        row.structured_json = json.dumps({"result": result.model_dump(), "facts": facts}, default=str)
        row.provider = provider
        s.flush()
        return SavedBriefing(
            date=today, provider=provider,
            created_at=row.created_at or dt.datetime.now(dt.timezone.utc),
            result=result, facts=facts,
        )


def latest_briefing() -> SavedBriefing | None:
    with session_scope() as s:
        row = s.execute(
            select(Briefing).order_by(Briefing.date.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        blob = json.loads(row.structured_json)
        return SavedBriefing(
            date=row.date, provider=row.provider, created_at=row.created_at,
            result=BriefingResult.model_validate(blob.get("result", {})),
            facts=blob.get("facts", {}),
        )
