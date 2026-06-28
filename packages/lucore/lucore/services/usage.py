"""LLM usage ledger — record each call's tokens/cost and summarize burn.

Lets the user watch how much of their Max-plan quota each feature consumes, so
they can avoid running out. Call `record(provider, kind, symbol)` right after any
provider.generate_json / .complete; it reads provider.last_meta and persists a row.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import func, select

from ..db import session_scope
from ..db.models import LlmCall
from ..llm.base import LLMProvider


def record(provider: LLMProvider, kind: str, symbol: str | None = None) -> None:
    """Persist the provider's most recent call metadata as an LlmCall row. No-op if absent."""
    meta = getattr(provider, "last_meta", None)
    if not meta:
        return
    with session_scope() as s:
        s.add(
            LlmCall(
                provider=meta.get("provider", provider.name),
                model=meta.get("model"),
                kind=kind,
                symbol=symbol,
                input_tokens=meta.get("input_tokens", 0),
                output_tokens=meta.get("output_tokens", 0),
                cache_read_tokens=meta.get("cache_read_tokens", 0),
                cache_creation_tokens=meta.get("cache_creation_tokens", 0),
                total_tokens=meta.get("total_tokens", 0),
                cost_usd=meta.get("cost_usd", 0.0),
                duration_ms=meta.get("duration_ms", 0),
                num_turns=meta.get("num_turns", 0),
            )
        )


class CallOut(BaseModel):
    id: int
    provider: str
    model: str | None
    kind: str
    symbol: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    duration_ms: int
    created_at: dt.datetime


class DayPoint(BaseModel):
    date: str
    calls: int
    total_tokens: int
    cost_usd: float


class UsageSummary(BaseModel):
    today_calls: int
    today_tokens: int
    today_cost_usd: float
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    by_kind: dict[str, int]  # kind -> call count
    by_day: list[DayPoint]   # last 14 days, oldest first
    recent: list[CallOut]


def summary(recent_limit: int = 30, days: int = 14) -> UsageSummary:
    today = dt.date.today()
    with session_scope() as s:
        total_calls = s.execute(select(func.count(LlmCall.id))).scalar_one() or 0
        total_tokens = s.execute(select(func.coalesce(func.sum(LlmCall.total_tokens), 0))).scalar_one() or 0
        total_cost = s.execute(select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0))).scalar_one() or 0.0

        rows = s.execute(
            select(LlmCall).order_by(LlmCall.created_at.desc()).limit(recent_limit)
        ).scalars().all()
        recent = [
            CallOut(
                id=r.id, provider=r.provider, model=r.model, kind=r.kind, symbol=r.symbol,
                input_tokens=r.input_tokens, output_tokens=r.output_tokens,
                total_tokens=r.total_tokens, cost_usd=r.cost_usd, duration_ms=r.duration_ms,
                created_at=r.created_at,
            )
            for r in rows
        ]

        # by_kind across all time
        kind_rows = s.execute(
            select(LlmCall.kind, func.count(LlmCall.id)).group_by(LlmCall.kind)
        ).all()
        by_kind = {k: c for k, c in kind_rows}

        # by_day + today via the recent-window scan (cheap for a personal DB)
        window = s.execute(
            select(LlmCall.created_at, LlmCall.total_tokens, LlmCall.cost_usd)
        ).all()

    buckets: dict[dt.date, list[int | float]] = {}
    today_calls = today_tokens = 0
    today_cost = 0.0
    for created, toks, cost in window:
        d = (created or dt.datetime.now(dt.timezone.utc)).date()
        b = buckets.setdefault(d, [0, 0, 0.0])
        b[0] += 1
        b[1] += toks or 0
        b[2] += cost or 0.0
        if d == today:
            today_calls += 1
            today_tokens += toks or 0
            today_cost += cost or 0.0

    by_day = [
        DayPoint(
            date=(d := today - dt.timedelta(days=i)).isoformat(),
            calls=buckets.get(d, [0, 0, 0.0])[0],
            total_tokens=buckets.get(d, [0, 0, 0.0])[1],
            cost_usd=round(buckets.get(d, [0, 0, 0.0])[2], 4),
        )
        for i in range(days - 1, -1, -1)
    ]

    return UsageSummary(
        today_calls=today_calls, today_tokens=today_tokens, today_cost_usd=round(today_cost, 4),
        total_calls=total_calls, total_tokens=int(total_tokens), total_cost_usd=round(float(total_cost), 4),
        by_kind=by_kind, by_day=by_day, recent=recent,
    )
