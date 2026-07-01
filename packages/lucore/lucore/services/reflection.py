"""Decision-reflection memory (TradingAgents-style): log each sized AI decision with the
price at decision time, then later grade whether the directional call played out against the
realized price move. All grading is deterministic Python (dual-brain); the LLM never scores
its own past calls here.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import select

from ..db import session_scope
from ..db.models import AgentDecision, Snapshot

# Actions that express a directional call (used to grade the outcome).
_LONG = {"buy", "add"}
_SHORT = {"sell", "trim"}


def log_decision(symbol: str, *, kind: str, action: str, stance: str | None,
                 score: float | None, price: float | None, provider: str | None = None,
                 today: dt.date | None = None) -> None:
    """Upsert one decision per symbol+kind+day."""
    sym = symbol.upper()
    day = (today or dt.date.today()).isoformat()
    with session_scope() as s:
        row = s.execute(
            select(AgentDecision).where(
                AgentDecision.symbol == sym, AgentDecision.kind == kind,
                AgentDecision.decided_on == day,
            )
        ).scalar_one_or_none()
        if row is None:
            row = AgentDecision(symbol=sym, kind=kind, decided_on=day)
            s.add(row)
            row.price = price  # anchor "price at decision" to the FIRST decision of the day
        # A re-run the same day updates the call but keeps the original decision price stable.
        row.action = action
        row.stance = stance
        row.score = score
        row.provider = provider


class ReflectionRow(BaseModel):
    symbol: str
    kind: str
    decided_on: str
    action: str
    stance: str | None = None
    score: float | None = None
    price: float | None = None
    current_price: float | None = None
    return_pct: float | None = None   # realized move since the decision
    grade: str = "open"               # hit | miss | open (no directional call) | na (no price)


class ReflectionSummary(BaseModel):
    rows: list[ReflectionRow] = []
    graded: int = 0                   # decisions with a directional call AND a realized price
    hits: int = 0
    hit_rate_pct: float | None = None
    avg_return_pct: float | None = None  # avg P&L-style realized move (short returns negated)


def _grade(action: str, ret: float | None) -> str:
    if ret is None:
        return "na"
    if action in _LONG:
        return "hit" if ret > 0 else "miss" if ret < 0 else "open"  # flat = not yet realized
    if action in _SHORT:
        return "hit" if ret < 0 else "miss" if ret > 0 else "open"
    return "open"  # hold / no directional call


def get_reflections(limit: int = 50) -> ReflectionSummary:
    with session_scope() as s:
        decisions = s.execute(
            select(AgentDecision).order_by(AgentDecision.decided_on.desc(), AgentDecision.id.desc())
            .limit(limit)
        ).scalars().all()
        # Detach the fields we need before the session closes.
        raw = [(d.symbol, d.kind, d.decided_on, d.action, d.stance, d.score, d.price)
               for d in decisions]
        # Batch-load current prices in one query (denormalized column — no JSON parse, no N+1).
        syms = {r[0] for r in raw}
        cur_prices = dict(
            s.execute(select(Snapshot.symbol, Snapshot.price).where(Snapshot.symbol.in_(syms))).all()
        ) if syms else {}

    rows: list[ReflectionRow] = []
    returns: list[float] = []  # direction-adjusted (P&L-style) realized moves
    hits = graded = 0
    for sym, kind, day, action, stance, score, price in raw:
        cur = cur_prices.get(sym)
        ret = round((cur - price) / price * 100, 2) if (cur and price) else None
        grade = _grade(action, ret)
        if grade in ("hit", "miss"):
            graded += 1
            if grade == "hit":
                hits += 1
            if ret is not None:
                # For a P&L-style average, a correct SHORT (price down) contributes positively.
                returns.append(ret if action in _LONG else -ret)
        rows.append(ReflectionRow(
            symbol=sym, kind=kind, decided_on=day, action=action, stance=stance,
            score=score, price=price, current_price=cur, return_pct=ret, grade=grade,
        ))

    return ReflectionSummary(
        rows=rows, graded=graded, hits=hits,
        hit_rate_pct=round(hits / graded * 100, 1) if graded else None,
        avg_return_pct=round(sum(returns) / len(returns), 2) if returns else None,
    )
