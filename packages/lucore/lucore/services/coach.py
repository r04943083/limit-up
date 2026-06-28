"""AI 投资教练 (#12).

Looks across the user's portfolio analytics, journal habits, paper activity and DNA,
then coaches on PROCESS — habits, behavioral biases, concrete drills and next actions.
Outcome-agnostic (it grades how you decide, not whether a pick won). Persisted to
`analyses` under kind='coach'.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import session_scope
from ..db.models import Analysis, JournalEntry
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import dna as dna_svc
from . import portfolio as pf
from . import paper, usage

ACCOUNT_KEY = "PORTFOLIO"


class CoachResult(BaseModel):
    grade: str = "B"  # letter grade on process
    discipline_score: float = Field(default=6.0, ge=0, le=10)
    headline: str = ""
    good_habits: list[str] = []
    biases: list[str] = []  # behavioral biases observed
    drills: list[str] = []  # concrete exercises to improve
    action_items: list[str] = []


class SavedCoach(BaseModel):
    provider: str
    created_at: dt.datetime
    result: CoachResult


def _gather() -> dict:
    pid = pf.ensure_default_portfolio()
    analytics = pf.get_analytics(pid)
    acct = paper.get_account()
    with session_scope() as s:
        journal = list(
            s.execute(select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(20)).scalars()
        )
        entries = [
            {"action": j.action, "symbol": j.symbol, "title": j.title,
             "conviction": j.conviction, "ai_score": j.ai_score}
            for j in journal
        ]
    dna = dna_svc.latest_dna()
    return {
        "portfolio": {
            "positions": len(analytics.positions), "top_weight": analytics.top_weight,
            "concentration_hhi": analytics.hhi, "sector_alloc": analytics.sector_alloc,
            "total_pnl_pct": analytics.total_pnl_pct,
        },
        "paper": {"trades": len(acct.trades), "return_pct": acct.total_return_pct},
        "journal": entries,
        "dna": dna.result.model_dump() if dna else None,
    }


_SPEC = {
    "grade": "letter grade A-F on DECISION PROCESS (not returns)",
    "discipline_score": "0-10",
    "headline": "one-sentence verdict on the user's process",
    "good_habits": ["habits worth keeping"],
    "biases": ["behavioral biases observed, e.g. overconcentration / chasing / no exit plan"],
    "drills": ["concrete practice exercises"],
    "action_items": ["specific next actions"],
}


def coach(*, provider: LLMProvider | None = None) -> SavedCoach:
    facts = _gather()
    provider = provider or get_provider()
    prompt = (
        "You are coaching this investor on PROCESS. Judge habits, risk discipline and behavioral "
        "biases from their actual data — not whether picks profited. Be specific and actionable.\n"
        f"DATA:\n{json.dumps(facts, indent=2, ensure_ascii=False, default=str)}\n\n"
        f"Return ONLY JSON:\n{json.dumps(_SPEC, indent=2, ensure_ascii=False)}"
    )
    system = with_chinese(
        "You are LU's investing coach — direct, supportive, focused on repeatable process and "
        "behavioral edge. JSON only."
    )
    result = CoachResult.model_validate(provider.generate_json(prompt, system=system))
    usage.record(provider, "coach", None)
    idem = dt.date.today().isoformat()
    with session_scope() as s:
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == ACCOUNT_KEY, Analysis.kind == "coach", Analysis.idempotency_key == idem,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=ACCOUNT_KEY, kind="coach", idempotency_key=idem)
            s.add(existing)
        existing.summary = result.headline
        existing.structured_json = result.model_dump_json()
        existing.provider = provider.name
        s.flush()
        return SavedCoach(provider=provider.name, created_at=existing.created_at, result=result)


def latest_coach() -> SavedCoach | None:
    with session_scope() as s:
        row = s.execute(
            select(Analysis).where(Analysis.symbol == ACCOUNT_KEY, Analysis.kind == "coach")
            .order_by(Analysis.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        return SavedCoach(
            provider=row.provider, created_at=row.created_at,
            result=CoachResult.model_validate_json(row.structured_json),
        )
