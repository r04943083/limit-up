"""Investment journal (#11).

The user logs decisions/observations (optionally tied to a symbol). LU can AI-grade
the *reasoning* of an entry — a write-back into the entry's ai_* columns — so the user
builds a feedback loop on their own decision quality over time.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import session_scope
from ..db.models import JournalEntry
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage

ACTIONS = ["buy", "sell", "add", "trim", "watch", "note"]


class JournalReview(BaseModel):
    score: float = Field(ge=0, le=10)  # quality of the decision *reasoning*
    verdict: str = ""  # one-line take
    strengths: list[str] = []
    blind_spots: list[str] = []
    biases: list[str] = []  # behavioral biases detected (FOMO, anchoring, ...)


class JournalOut(BaseModel):
    id: int
    symbol: str | None
    action: str
    title: str
    body: str | None
    conviction: str | None
    ai_score: float | None
    ai_review: JournalReview | None
    created_at: dt.datetime


def _to_out(row: JournalEntry) -> JournalOut:
    review = JournalReview.model_validate_json(row.ai_review_json) if row.ai_review_json else None
    return JournalOut(
        id=row.id, symbol=row.symbol, action=row.action, title=row.title, body=row.body,
        conviction=row.conviction, ai_score=row.ai_score, ai_review=review, created_at=row.created_at,
    )


def list_entries(symbol: str | None = None, limit: int = 100) -> list[JournalOut]:
    with session_scope() as s:
        q = select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(limit)
        if symbol:
            q = q.where(JournalEntry.symbol == symbol.upper())
        return [_to_out(r) for r in s.execute(q).scalars()]


def add_entry(
    *, title: str, body: str | None = None, symbol: str | None = None,
    action: str = "note", conviction: str | None = None,
) -> JournalOut:
    with session_scope() as s:
        row = JournalEntry(
            title=title.strip(), body=(body or "").strip() or None,
            symbol=symbol.upper() if symbol else None,
            action=action if action in ACTIONS else "note", conviction=conviction,
        )
        s.add(row)
        s.flush()
        return _to_out(row)


def delete_entry(entry_id: int) -> bool:
    with session_scope() as s:
        row = s.get(JournalEntry, entry_id)
        if row is None:
            return False
        s.delete(row)
        return True


def review_entry(entry_id: int, *, provider: LLMProvider | None = None) -> JournalOut | None:
    """AI-grade an entry's reasoning. Reads the entry, asks the LLM to critique the decision
    process (not predict the outcome), validates, and writes back into the row."""
    with session_scope() as s:
        row = s.get(JournalEntry, entry_id)
        if row is None:
            return None
        facts = {
            "symbol": row.symbol, "action": row.action, "title": row.title,
            "rationale": row.body, "stated_conviction": row.conviction,
        }
    provider = provider or get_provider()
    spec = {
        "score": "0-10 quality of the REASONING (not whether it will be right)",
        "verdict": "one short sentence",
        "strengths": ["what is sound about the thinking"],
        "blind_spots": ["what the rationale misses"],
        "biases": ["behavioral biases visible, e.g. FOMO / anchoring / recency / confirmation"],
    }
    prompt = (
        "Critique the decision-making process in this investment journal entry. Judge the QUALITY "
        "of the reasoning and risk-awareness, not whether the trade will profit.\n"
        f"ENTRY:\n{json.dumps(facts, indent=2, ensure_ascii=False)}\n\n"
        f"Return ONLY JSON:\n{json.dumps(spec, indent=2)}"
    )
    system = with_chinese(
        "You are LU's investing coach. Be constructive but candid about reasoning quality and "
        "behavioral biases. JSON only."
    )
    review = JournalReview.model_validate(provider.generate_json(prompt, system=system))
    usage.record(provider, "journal", row.symbol)
    with session_scope() as s:
        row = s.get(JournalEntry, entry_id)
        if row is None:
            return None
        row.ai_score = review.score
        row.ai_review_json = review.model_dump_json()
        row.provider = provider.name
        s.flush()
        return _to_out(row)
