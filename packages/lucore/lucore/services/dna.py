"""投资记忆 / 投资 DNA (#16).

Derives a deterministic behavioral profile from what the user actually does — holdings
mix, watchlist tilt, journal actions/conviction, paper-trade activity — then has the
LLM narrate it as an investor "DNA". Persisted to `analyses` under kind='dna'.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import session_scope
from ..db.models import Analysis, JournalEntry, WatchlistItem
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import portfolio as pf
from . import paper, usage

ACCOUNT_KEY = "PORTFOLIO"


class DnaResult(BaseModel):
    archetype: str = ""  # e.g. "成长型趋势交易者"
    risk_tolerance: str = "medium"  # low | medium | high
    time_horizon: str = ""  # e.g. "中长期"
    sector_tilt: list[str] = []
    strengths: list[str] = []
    watchouts: list[str] = []
    summary: str = ""
    growth_vs_value: float = Field(default=50.0, ge=0, le=100)  # 0=deep value, 100=hyper growth
    conviction: float = Field(default=50.0, ge=0, le=100)  # diversified .. concentrated


class SavedDna(BaseModel):
    provider: str
    created_at: dt.datetime
    facts: dict
    result: DnaResult


def gather_facts() -> dict:
    """Deterministic behavioral facts (no LLM, no network)."""
    pid = pf.ensure_default_portfolio()
    analytics = pf.get_analytics(pid)
    acct = paper.get_account()
    with session_scope() as s:
        wl_items = list(s.execute(select(WatchlistItem)).scalars())
        tags: dict[str, int] = {}
        for it in wl_items:
            for t in (it.tags or "").split(","):
                t = t.strip()
                if t:
                    tags[t] = tags.get(t, 0) + 1
        journal = list(s.execute(select(JournalEntry)).scalars())
        action_counts: dict[str, int] = {}
        convs = {"low": 0, "medium": 0, "high": 0}
        scores = [j.ai_score for j in journal if j.ai_score is not None]
        for j in journal:
            action_counts[j.action] = action_counts.get(j.action, 0) + 1
            if j.conviction in convs:
                convs[j.conviction] += 1
    return {
        "holdings_count": len(analytics.positions),
        "sector_alloc": analytics.sector_alloc,
        "market_alloc": analytics.market_alloc,
        "top_weight": analytics.top_weight,
        "concentration_hhi": analytics.hhi,
        "total_pnl_pct": analytics.total_pnl_pct,
        "watchlist_size": len(wl_items),
        "watchlist_tags": dict(sorted(tags.items(), key=lambda kv: -kv[1])[:8]),
        "journal_actions": action_counts,
        "journal_conviction": convs,
        "journal_avg_reasoning_score": (sum(scores) / len(scores)) if scores else None,
        "paper_trades": len(acct.trades),
        "paper_return_pct": acct.total_return_pct,
        "paper_positions": len(acct.positions),
    }


_SPEC = {
    "archetype": "a vivid 4-8 char投资者画像, e.g. '价值长持者' / '成长趋势交易者'",
    "risk_tolerance": "low | medium | high",
    "time_horizon": "短线 | 波段 | 中长期 | 长期",
    "sector_tilt": ["dominant sectors the behavior reveals"],
    "strengths": ["behavioral strengths"],
    "watchouts": ["behavioral risks / blind spots"],
    "summary": "2-4 sentence portrait of this investor",
    "growth_vs_value": "0 (deep value) .. 100 (hyper growth)",
    "conviction": "0 (very diversified) .. 100 (very concentrated)",
}


def compute_dna(*, provider: LLMProvider | None = None) -> SavedDna:
    facts = gather_facts()
    provider = provider or get_provider()
    prompt = (
        "Read this investor's actual behavior (holdings mix, watchlist tilt, journal habits, paper "
        "activity) and distill their investing DNA. Base it ONLY on the facts.\n"
        f"BEHAVIOR:\n{json.dumps(facts, indent=2, ensure_ascii=False, default=str)}\n\n"
        f"Return ONLY JSON:\n{json.dumps(_SPEC, indent=2, ensure_ascii=False)}"
    )
    system = with_chinese(
        "You are LU's investor-profiling brain. Infer personality from behavior, be specific and "
        "kind but honest. JSON only."
    )
    result = DnaResult.model_validate(provider.generate_json(prompt, system=system))
    usage.record(provider, "dna", None)
    idem = dt.date.today().isoformat()
    with session_scope() as s:
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == ACCOUNT_KEY, Analysis.kind == "dna", Analysis.idempotency_key == idem,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=ACCOUNT_KEY, kind="dna", idempotency_key=idem)
            s.add(existing)
        existing.summary = result.summary
        existing.structured_json = result.model_dump_json()
        existing.provider = provider.name
        s.flush()
        return SavedDna(provider=provider.name, created_at=existing.created_at, facts=facts, result=result)


def latest_dna() -> SavedDna | None:
    with session_scope() as s:
        row = s.execute(
            select(Analysis).where(Analysis.symbol == ACCOUNT_KEY, Analysis.kind == "dna")
            .order_by(Analysis.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        result = DnaResult.model_validate_json(row.structured_json)
    return SavedDna(provider=row.provider, created_at=row.created_at, facts=gather_facts(), result=result)
