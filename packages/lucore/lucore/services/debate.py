"""AI 多空辩论 (#19).

A bull seat and a bear seat argue over the SAME deterministic facts, each rebuts the
other, then an impartial judge declares a winner and a calibrated verdict. One batched
claude -p call returns the whole transcript (fast + cheap); persisted to `analyses`
under kind='debate'.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import session_scope
from ..db.models import Analysis
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage
from .analyze import _facts
from .research import get_research


class DebateResult(BaseModel):
    bull_case: str
    bear_case: str
    bull_rebuttal: str = ""
    bear_rebuttal: str = ""
    winner: str = "draw"  # bull | bear | draw
    confidence: float = Field(default=5.0, ge=0, le=10)
    verdict: str = ""  # the judge's synthesis
    key_question: str = ""  # the one thing that decides it


class SavedDebate(BaseModel):
    symbol: str
    provider: str
    created_at: dt.datetime
    result: DebateResult


_SPEC = {
    "bull_case": "strongest bull argument grounded in the facts",
    "bear_case": "strongest bear argument grounded in the facts",
    "bull_rebuttal": "bull's answer to the bear",
    "bear_rebuttal": "bear's answer to the bull",
    "winner": "bull | bear | draw",
    "confidence": "0-10 how decisive the win is",
    "verdict": "impartial judge's 2-3 sentence synthesis",
    "key_question": "the single question that, once answered, settles the debate",
}


def run_debate(symbol: str, *, provider: LLMProvider | None = None) -> SavedDebate:
    bundle = get_research(symbol, cached=True)  # cache-first: reliable + no rate-limit 500s
    provider = provider or get_provider()
    prompt = (
        f"Stage a rigorous bull-vs-bear debate on {bundle.symbol}, then judge it. Both sides argue "
        f"ONLY from these facts (ground truth) — no invented numbers:\n"
        f"{json.dumps(_facts(bundle), indent=2, default=str)}\n\n"
        f"Return ONLY JSON:\n{json.dumps(_SPEC, indent=2)}"
    )
    system = with_chinese(
        "You are LU's debate moderator running three roles: a sharp BULL, a sharp BEAR, and an "
        "impartial JUDGE. Make each side genuinely adversarial and concrete. JSON only."
    )
    result = DebateResult.model_validate(provider.generate_json(prompt, system=system))
    usage.record(provider, "debate", symbol)
    return _persist(symbol, result, provider.name)


def _persist(symbol: str, result: DebateResult, provider: str) -> SavedDebate:
    sym = symbol.upper()
    idem = dt.date.today().isoformat()
    with session_scope() as s:
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == sym, Analysis.kind == "debate", Analysis.idempotency_key == idem,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=sym, kind="debate", idempotency_key=idem)
            s.add(existing)
        existing.summary = result.verdict
        existing.structured_json = result.model_dump_json()
        existing.provider = provider
        s.flush()
        return SavedDebate(symbol=sym, provider=provider, created_at=existing.created_at, result=result)


def latest_debate(symbol: str) -> SavedDebate | None:
    with session_scope() as s:
        row = s.execute(
            select(Analysis).where(Analysis.symbol == symbol.upper(), Analysis.kind == "debate")
            .order_by(Analysis.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        return SavedDebate(
            symbol=row.symbol, provider=row.provider, created_at=row.created_at,
            result=DebateResult.model_validate_json(row.structured_json),
        )
