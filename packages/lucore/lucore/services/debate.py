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
from .personas import get_persona
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
    # Optional persona seating: which investor archetype argued each side ("" = generic seat).
    # Filled server-side from the registry — never trusted from the model.
    bull_persona: str = ""
    bear_persona: str = ""
    bull_persona_name: str = ""
    bear_persona_name: str = ""


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


def run_debate(
    symbol: str, *, bull_persona: str | None = None, bear_persona: str | None = None,
    provider: LLMProvider | None = None,
) -> SavedDebate:
    bundle = get_research(symbol, cached=True)  # cache-first: reliable + no rate-limit 500s
    provider = provider or get_provider()

    # Optional persona seating: a specific investor archetype argues each side. Unknown keys
    # are ignored (fall back to a generic seat) so a bad key never fails the debate.
    bull_p = get_persona(bull_persona) if bull_persona else None
    bear_p = get_persona(bear_persona) if bear_persona else None
    seats = ""
    if bull_p:
        seats += f"\nThe BULL argues strictly in character as {bull_p.name}: {bull_p.system}"
    if bear_p:
        seats += f"\nThe BEAR argues strictly in character as {bear_p.name}: {bear_p.system}"

    prompt = (
        f"Stage a rigorous bull-vs-bear debate on {bundle.symbol}, then judge it. Both sides argue "
        f"ONLY from these facts (ground truth) — no invented numbers:\n"
        f"{json.dumps(_facts(bundle), indent=2, default=str)}\n"
        f"{seats}\n\n"
        f"Return ONLY JSON:\n{json.dumps(_SPEC, indent=2)}"
    )
    system = with_chinese(
        "You are LU's debate moderator running three roles: a sharp BULL, a sharp BEAR, and an "
        "impartial JUDGE. Make each side genuinely adversarial and concrete. Judge on the merits "
        "of the arguments, not on which persona is seated. JSON only."
    )
    result = DebateResult.model_validate(provider.generate_json(prompt, system=system))
    # Stamp the seating from the registry (not the model) so the UI can label each side.
    result = result.model_copy(update={
        "bull_persona": bull_p.key if bull_p else "",
        "bear_persona": bear_p.key if bear_p else "",
        "bull_persona_name": bull_p.name if bull_p else "",
        "bear_persona_name": bear_p.name if bear_p else "",
    })
    usage.record(provider, "debate", symbol)
    return _persist(symbol, result, provider.name)


def _persist(symbol: str, result: DebateResult, provider: str) -> SavedDebate:
    sym = symbol.upper()
    # One debate per (symbol, seating) per day — so re-running the SAME matchup is idempotent,
    # but a different persona pairing on the same day is kept as its own row.
    idem = f"{dt.date.today().isoformat()}:{result.bull_persona or '-'}:{result.bear_persona or '-'}"
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
