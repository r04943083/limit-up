"""多智能体投研 (#14).

A panel of specialist agents — fundamental, technical, sentiment, risk, macro — each
assesses the SAME deterministic facts from its own angle, then a chief strategist
synthesizes a house view with a blended score. One batched claude -p call; persisted to
`analyses` under kind='multiagent'.
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
from .research import build_research_bundle

AGENTS = ["fundamental", "technical", "sentiment", "risk", "macro"]
_AGENT_LABEL = {
    "fundamental": "基本面", "technical": "技术面", "sentiment": "情绪/新闻",
    "risk": "风险", "macro": "宏观",
}


class AgentView(BaseModel):
    agent: str
    stance: str = "neutral"  # bullish | neutral | bearish
    score: float = Field(default=5.0, ge=0, le=10)
    rationale: str = ""


class MultiAgentResult(BaseModel):
    agents: list[AgentView] = []
    consensus_score: float = Field(default=5.0, ge=0, le=10)
    recommendation: str = "Hold"
    synthesis: str = ""
    disagreement: str = ""  # where the agents disagree most


class SavedMultiAgent(BaseModel):
    symbol: str
    provider: str
    created_at: dt.datetime
    result: MultiAgentResult


def agent_label(key: str) -> str:
    return _AGENT_LABEL.get(key, key)


_SPEC = {
    "agents": [{
        "agent": "one of: " + " | ".join(AGENTS),
        "stance": "bullish | neutral | bearish",
        "score": "0-10 from THIS agent's lens",
        "rationale": "2-3 sentences grounded in the facts",
    }],
    "consensus_score": "0-10 blended house score",
    "recommendation": "Strong Buy | Buy | Hold | Sell | Strong Sell",
    "synthesis": "chief strategist's 2-4 sentence house view",
    "disagreement": "where the agents most disagree and why it matters",
}


def run_panel(symbol: str, *, provider: LLMProvider | None = None) -> SavedMultiAgent:
    bundle = build_research_bundle(symbol)
    provider = provider or get_provider()
    prompt = (
        f"Convene a research panel on {bundle.symbol}. Produce one view per agent in "
        f"[{', '.join(AGENTS)}], then a chief-strategist synthesis. All agents reason ONLY over "
        f"these facts (ground truth):\n{json.dumps(_facts(bundle), indent=2, default=str)}\n\n"
        f"Return ONLY JSON:\n{json.dumps(_SPEC, indent=2)}"
    )
    system = with_chinese(
        "You are LU's multi-agent investment committee. Each specialist must stay in its lane and "
        "be concrete; the chief strategist reconciles them. Return EXACTLY one entry per agent. JSON only."
    )
    result = MultiAgentResult.model_validate(provider.generate_json(prompt, system=system))
    usage.record(provider, "multiagent", symbol)
    return _persist(symbol, result, provider.name)


def _persist(symbol: str, result: MultiAgentResult, provider: str) -> SavedMultiAgent:
    sym = symbol.upper()
    idem = dt.date.today().isoformat()
    with session_scope() as s:
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == sym, Analysis.kind == "multiagent", Analysis.idempotency_key == idem,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=sym, kind="multiagent", idempotency_key=idem)
            s.add(existing)
        existing.summary = result.synthesis
        existing.structured_json = result.model_dump_json()
        existing.provider = provider
        s.flush()
        return SavedMultiAgent(symbol=sym, provider=provider, created_at=existing.created_at, result=result)


def latest_panel(symbol: str) -> SavedMultiAgent | None:
    with session_scope() as s:
        row = s.execute(
            select(Analysis).where(Analysis.symbol == symbol.upper(), Analysis.kind == "multiagent")
            .order_by(Analysis.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        return SavedMultiAgent(
            symbol=row.symbol, provider=row.provider, created_at=row.created_at,
            result=MultiAgentResult.model_validate_json(row.structured_json),
        )
