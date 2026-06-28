"""Recommendation service: deterministic screen of a universe, then ONE batched
claude -p call to score + write theses for the survivors, persisted to `recommendations`.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..compute.screener import Candidate, ScreenInput, screen
from ..data.router import get_router
from ..db import session_scope
from ..db.models import Recommendation
from ..llm.base import LLMProvider, get_provider
from ..services.research import get_technical

# Modest curated universe (US + a few HK). Extend / move to DB later.
SEED_UNIVERSE = [
    "NVDA", "AMD", "AVGO", "MSFT", "AAPL", "GOOGL", "META", "AMZN", "TSLA", "NFLX",
    "AVTR", "JPM", "V", "MA", "KO", "PEP", "JNJ", "PG", "XOM", "CVX",
    "COST", "WMT", "PLTR", "CRWD", "0700.HK", "9988.HK",
]


class RecoItem(BaseModel):
    symbol: str
    ai_score: float = Field(ge=0, le=10)
    conviction: str = "medium"
    thesis: str
    risks: list[str] = []
    catalysts: list[str] = []
    target_price: float | None = None
    time_horizon: str | None = None


class RecoBatch(BaseModel):
    recommendations: list[RecoItem] = []


class RecommendationOut(BaseModel):
    symbol: str
    category: str
    name: str | None = None
    ai_score: float | None
    conviction: str | None
    thesis: str | None
    risks: list[str] = []
    catalysts: list[str] = []
    target_price: float | None
    time_horizon: str | None
    provider: str


def _screen_input(symbol: str) -> ScreenInput | None:
    router = get_router()
    try:
        f = router.get_fundamentals(symbol)
        ta = get_technical(symbol)
    except Exception:
        return None
    latest = ta.latest
    return ScreenInput(
        symbol=symbol, name=f.name, sector=f.sector,
        pe_ttm=f.pe_ttm, pb=f.pb, ps=f.ps, peg=f.peg,
        revenue_growth=f.revenue_growth, earnings_growth=f.earnings_growth,
        gross_margin=f.gross_margin, net_margin=f.net_margin, roe=f.roe,
        dividend_yield=f.dividend_yield, market_cap=f.market_cap,
        trend=ta.trend, rsi=latest.get("rsi14"), price=latest.get("price"),
        sma50=latest.get("sma50"), sma200=latest.get("sma200"),
    )


def screen_category(category: str, universe: list[str] | None = None, top_n: int = 6) -> list[Candidate]:
    universe = universe or SEED_UNIVERSE
    inputs = [si for s in universe if (si := _screen_input(s)) is not None]
    return screen(category, inputs, top_n=top_n)


def _facts_for(candidates: list[Candidate]) -> list[dict]:
    router = get_router()
    facts = []
    for c in candidates:
        f = router.get_fundamentals(c.symbol)
        ta = get_technical(c.symbol)
        facts.append({
            "symbol": c.symbol, "name": c.name, "matched": c.reasons,
            "price": ta.latest.get("price"), "pe_ttm": f.pe_ttm, "pe_fwd": f.pe_fwd,
            "ps": f.ps, "peg": f.peg, "revenue_growth": f.revenue_growth,
            "net_margin": f.net_margin, "roe": f.roe, "dividend_yield": f.dividend_yield,
            "trend": ta.trend, "rsi": ta.latest.get("rsi14"),
            "analyst_rec": f.recommendation, "target_mean": f.target_mean,
        })
    return facts


def generate(category: str, universe: list[str] | None = None, top_n: int = 5, *, provider: LLMProvider | None = None) -> list[RecommendationOut]:
    candidates = screen_category(category, universe=universe, top_n=top_n)
    if not candidates:
        return []
    provider = provider or get_provider()
    facts = _facts_for(candidates)
    spec = {
        "recommendations": [{
            "symbol": "ticker", "ai_score": "0-10 attractiveness now", "conviction": "low|medium|high",
            "thesis": "2-3 sentence thesis grounded in the facts", "risks": ["bullets"],
            "catalysts": ["bullets"], "target_price": "number or null", "time_horizon": "e.g. 6-12 months",
        }]
    }
    prompt = (
        f"You are screening for the '{category}' category. These candidates PASSED LU's deterministic "
        f"screen. FACTS (ground truth):\n{json.dumps(facts, indent=2, default=str)}\n\n"
        f"Score and justify each. Return ONLY JSON of this shape:\n{json.dumps(spec, indent=2)}"
    )
    system = (
        "You are LU's recommendation analyst. Only reason over the provided facts; never invent numbers. "
        "Return a recommendation for EACH candidate. JSON only."
    )
    batch = RecoBatch.model_validate(provider.generate_json(prompt, system=system))

    by_symbol = {c.symbol: c for c in candidates}
    idem = dt.date.today().isoformat()
    out: list[RecommendationOut] = []
    with session_scope() as s:
        for item in batch.recommendations:
            sym = item.symbol.upper()
            if sym not in by_symbol:
                continue
            existing = s.execute(
                select(Recommendation).where(
                    Recommendation.symbol == sym, Recommendation.category == category,
                    Recommendation.idempotency_key == idem,
                )
            ).scalar_one_or_none()
            if existing is None:
                existing = Recommendation(symbol=sym, category=category, idempotency_key=idem)
                s.add(existing)
            existing.ai_score = item.ai_score
            existing.conviction = item.conviction
            existing.thesis = item.thesis
            existing.risks_json = json.dumps(item.risks)
            existing.catalysts_json = json.dumps(item.catalysts)
            existing.target_price = item.target_price
            existing.time_horizon = item.time_horizon
            existing.provider = provider.name
            out.append(RecommendationOut(
                symbol=sym, category=category, name=by_symbol[sym].name, ai_score=item.ai_score,
                conviction=item.conviction, thesis=item.thesis, risks=item.risks, catalysts=item.catalysts,
                target_price=item.target_price, time_horizon=item.time_horizon, provider=provider.name,
            ))
    return out


def list_recommendations(category: str | None = None, limit: int = 50) -> list[RecommendationOut]:
    with session_scope() as s:
        q = select(Recommendation).order_by(Recommendation.ai_score.desc().nullslast())
        if category:
            q = q.where(Recommendation.category == category)
        rows = s.execute(q.limit(limit)).scalars().all()
        return [
            RecommendationOut(
                symbol=r.symbol, category=r.category, ai_score=r.ai_score, conviction=r.conviction,
                thesis=r.thesis, risks=json.loads(r.risks_json or "[]"), catalysts=json.loads(r.catalysts_json or "[]"),
                target_price=r.target_price, time_horizon=r.time_horizon, provider=r.provider,
            )
            for r in rows
        ]
