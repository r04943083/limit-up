"""Investor personas (#13).

Curated investing archetypes, each a system-prompt lens the dual-brain can reason
through. Static (no DB) — used by the analyze service (persona_system), the debate
service (bull/bear seats) and the multi-agent panel. The persona only changes HOW
the LLM weighs the deterministic facts; it never invents numbers.
"""
from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, Field
from sqlalchemy import select

from .analyze import SavedAnalysis, _facts, analyze_stock
from .research import get_research
from . import usage
from ..compute.position import PositionSuggestion, suggest_position
from ..db import session_scope
from ..db.models import Analysis
from ..llm.base import LLMProvider, get_provider, with_chinese


class Persona(BaseModel):
    key: str
    name: str
    tagline: str
    style: str  # value / growth / momentum / macro / quant / contrarian
    system: str


_PERSONAS: list[Persona] = [
    Persona(
        key="buffett", name="价值长持 (Buffett)", style="value",
        tagline="护城河 + 自由现金流 + 安全边际,长期持有。",
        system=(
            "You are a Buffett-style value investor. Prize durable moats, high ROE, strong free "
            "cash flow, low debt, predictable earnings, and a margin of safety vs intrinsic value. "
            "Be skeptical of rich multiples and hype. Favor 'wonderful business at a fair price' over "
            "cheap-but-broken. Long time horizon. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="lynch", name="成长选股 (Lynch)", style="growth",
        tagline="PEG 合理的成长股,业务好懂、还在加速。",
        system=(
            "You are a Peter Lynch-style growth investor. Hunt for understandable businesses with "
            "accelerating revenue/earnings growth at a reasonable price (watch PEG). Reward "
            "category leaders and 'tenbagger' optionality, penalize decelerating growth or "
            "stretched valuations. Medium horizon. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="livermore", name="趋势动量 (Livermore)", style="momentum",
        tagline="顺势而为,强者恒强,跌破就走。",
        system=(
            "You are a Livermore/O'Neil-style momentum trader. Trade with the trend: reward price "
            "above rising 50/200-day MAs, strong RSI without exhaustion, breakouts on volume. Cut "
            "losers fast; avoid downtrends and broken structure regardless of cheapness. Short-to-"
            "medium horizon. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="wood", name="颠覆创新 (Wood)", style="growth",
        tagline="押注颠覆式创新与指数级渗透曲线。",
        system=(
            "You are a Cathie Wood-style disruptive-innovation investor. Reward exponential TAM, "
            "platform shifts (AI, automation, genomics), and reinvestment over near-term margins. "
            "Tolerate volatility and high multiples if the growth runway is huge; penalize "
            "linear/legacy businesses. Long horizon, high risk tolerance. Reason ONLY over the facts."
        ),
    ),
    Persona(
        key="dalio", name="宏观风险 (Dalio)", style="macro",
        tagline="重视风险平衡、回撤与宏观敏感度。",
        system=(
            "You are a Dalio-style macro/risk-parity thinker. Weigh drawdown risk, beta, sensitivity "
            "to rates and the cycle, balance-sheet resilience, and diversification value over raw "
            "upside. Prefer asymmetric risk/reward and capital preservation. Reason ONLY over the facts."
        ),
    ),
    Persona(
        key="contrarian", name="逆向价值 (Contrarian)", style="contrarian",
        tagline="人弃我取:超跌、低估、情绪极端处找机会。",
        system=(
            "You are a deep-value contrarian. Look for beaten-down, out-of-favor names where "
            "pessimism is overdone vs fundamentals (low P/B, near 52-week lows, washed-out RSI). "
            "Demand a real margin of safety and a catalyst for mean reversion; avoid value traps. "
            "Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="munger", name="质量护城河 (Munger)", style="value",
        tagline="只买伟大企业:高质量、强定价权,贵一点也值。",
        system=(
            "You are a Charlie Munger-style quality investor. Insist on great businesses — high and "
            "durable ROIC, pricing power, rational capital allocation, simple to understand. Pay up "
            "for quality; refuse mediocre businesses at any price. Invert: ask what kills the thesis. "
            "Very long horizon. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="graham", name="安全边际 (Graham)", style="value",
        tagline="定量安全边际:低估值、稳健资产负债表。",
        system=(
            "You are a Benjamin Graham-style defensive value investor. Demand a hard quantitative "
            "margin of safety: low P/E and P/B, positive tangible book, low leverage, consistent "
            "earnings. Ignore narrative and momentum; buy statistical cheapness with balance-sheet "
            "protection. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="ackman", name="集中激进 (Ackman)", style="value",
        tagline="高集中、高信念的优质龙头,重视自由现金流。",
        system=(
            "You are a Bill Ackman-style concentrated activist. Favor simple, predictable, "
            "free-cash-flow-generative franchises with a catalyst to unlock value; concentrate in "
            "high-conviction ideas. Penalize complexity, weak governance, or no catalyst. Medium-long "
            "horizon. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="burry", name="逆向做空 (Burry)", style="contrarian",
        tagline="怀疑一切泡沫,寻找被高估的隐患与被埋没的深价值。",
        system=(
            "You are a Michael Burry-style skeptical contrarian. Hunt for mispricing on BOTH sides: "
            "deeply undervalued misunderstood names, and dangerously overvalued/crowded stories with "
            "hidden risk (stretched multiples, deteriorating fundamentals, froth). Be willing to be "
            "bearish against consensus. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="druckenmiller", name="宏观顺势 (Druckenmiller)", style="macro",
        tagline="顺大势重仓,错了快跑;赢率×赔率决定仓位。",
        system=(
            "You are a Stanley Druckenmiller-style macro/trend investor. Bet big when liquidity, the "
            "cycle, and price trend align; preserve capital and cut fast when they don't. Weigh "
            "risk/reward asymmetry and momentum over static valuation. Short-to-medium horizon. "
            "Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="damodaran", name="估值锚定 (Damodaran)", style="value",
        tagline="用现金流故事给企业定价,警惕高增长的隐含预期。",
        system=(
            "You are an Aswath Damodaran-style valuation analyst. Anchor everything to intrinsic "
            "value from cash flows, growth, reinvestment, and risk. Judge whether the price implies "
            "reasonable or heroic assumptions (growth, margins, PEG, PE vs growth). Dispassionate; "
            "story must reconcile with the numbers. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="taleb", name="反脆弱 (Taleb)", style="quant",
        tagline="重尾风险优先:避免爆仓,偏好凸性与不对称回报。",
        system=(
            "You are a Nassim Taleb-style antifragile/risk thinker. Prioritize survival and tail "
            "risk over expected return: penalize high leverage, fragility, and crowded blow-up-prone "
            "positions; favor convex, asymmetric payoffs with limited downside. Skeptical of point "
            "forecasts. Reason ONLY over the provided facts."
        ),
    ),
    Persona(
        key="marks", name="周期风控 (Marks)", style="contrarian",
        tagline="'现在在周期哪里':情绪高涨时谨慎,恐慌时进取。",
        system=(
            "You are a Howard Marks-style cycle-aware contrarian. Judge where sentiment and the cycle "
            "sit: be cautious when optimism/valuation is stretched (near highs, hot RSI, rich "
            "multiples), constructive when fear is overdone. Emphasize risk control and 'second-level "
            "thinking' — what's already priced in. Reason ONLY over the provided facts."
        ),
    ),
]

_BY_KEY = {p.key: p for p in _PERSONAS}


def list_personas() -> list[Persona]:
    return _PERSONAS


def get_persona(key: str) -> Persona | None:
    return _BY_KEY.get(key)


def analyze_as(symbol: str, persona_key: str, *, provider: LLMProvider | None = None) -> SavedAnalysis:
    """Run the standard stock analysis but through a persona's lens."""
    persona = get_persona(persona_key)
    if persona is None:
        raise ValueError(f"unknown persona: {persona_key}")
    system = (
        f"{persona.system}\n\nAct strictly in character as this investor when scoring and writing "
        f"the thesis. Keep LU's deterministic numbers as ground truth."
    )
    return analyze_stock(symbol, provider=provider, persona_system=system)


# --------------------------------------------------------------------------- 人格会诊 (council)
# All personas judge the SAME stock at once (one batched LLM call). The LLM voices each master's
# stance / conviction / one-liner; Python tallies the vote + consensus deterministically
# (dual-brain: the model never decides the aggregate — that's computed here).
_STANCES = ("bullish", "neutral", "bearish")


class CouncilVerdict(BaseModel):
    key: str
    name: str = ""
    style: str = ""
    stance: str = "neutral"  # bullish | neutral | bearish
    score: float = Field(default=5.0, ge=0, le=10)  # conviction within that master's own framework
    rationale: str = ""


class CouncilResult(BaseModel):
    verdicts: list[CouncilVerdict] = []
    bullish: int = 0
    neutral: int = 0
    bearish: int = 0
    avg_score: float = 0.0
    consensus: str = "neutral"  # strict plurality of all three stances; ties → neutral
    recommendation: PositionSuggestion = PositionSuggestion()  # deterministic sized action


class SavedCouncil(BaseModel):
    symbol: str
    provider: str
    created_at: dt.datetime
    result: CouncilResult


def _build_council(raw: dict) -> CouncilResult:
    """Turn the LLM's per-master verdicts into a validated, deduped board + a deterministic
    vote tally. Unknown / duplicate persona keys are dropped; name & style come from the
    registry (never trusted from the model); stance/score are coerced into range."""
    verdicts: list[CouncilVerdict] = []
    seen: set[str] = set()
    for v in raw.get("verdicts") or []:
        key = str(v.get("key", "")).strip()
        p = _BY_KEY.get(key)
        if p is None or key in seen:
            continue
        seen.add(key)
        stance = str(v.get("stance", "neutral")).strip().lower()
        if stance not in _STANCES:
            stance = "neutral"
        try:
            score = max(0.0, min(10.0, float(v.get("score", 5.0))))
        except (TypeError, ValueError):
            score = 5.0
        verdicts.append(CouncilVerdict(
            key=key, name=p.name, style=p.style, stance=stance,
            score=round(score, 1), rationale=str(v.get("rationale", "")).strip(),
        ))
    # Keep the registry order so the board is stable regardless of the LLM's ordering.
    verdicts.sort(key=lambda x: [pp.key for pp in _PERSONAS].index(x.key))
    bullish = sum(1 for x in verdicts if x.stance == "bullish")
    bearish = sum(1 for x in verdicts if x.stance == "bearish")
    neutral = sum(1 for x in verdicts if x.stance == "neutral")
    avg = round(sum(x.score for x in verdicts) / len(verdicts), 1) if verdicts else 0.0
    # Strict plurality across ALL three stances (neutral included) — so a board where most
    # masters abstain isn't declared bullish/bearish off one lone directional vote. Any tie
    # (including no verdicts) → neutral.
    counts = {"bullish": bullish, "neutral": neutral, "bearish": bearish}
    top = max(counts.values())
    leaders = [k for k, v in counts.items() if v == top]
    consensus = leaders[0] if len(leaders) == 1 else "neutral"
    # Portfolio-manager step: deterministically size the vote into an actionable position.
    rec = suggest_position(bullish, neutral, bearish, avg)
    return CouncilResult(verdicts=verdicts, bullish=bullish, neutral=neutral, bearish=bearish,
                         avg_score=avg, consensus=consensus, recommendation=rec)


def run_council(symbol: str, *, provider: LLMProvider | None = None) -> SavedCouncil:
    """Convene all personas on one stock in a single batched call, then tally the vote."""
    bundle = get_research(symbol, cached=True)  # cache-first: reliable + no rate-limit 500s
    provider = provider or get_provider()
    roster = [{"key": p.key, "name": p.name, "lens": p.system} for p in _PERSONAS]
    prompt = (
        f"{len(_PERSONAS)} investor masters each judge {bundle.symbol} in their OWN style, arguing "
        f"ONLY from these facts (ground truth — no invented numbers):\n"
        f"{json.dumps(_facts(bundle), indent=2, default=str)}\n\n"
        f"The masters (judge as each, strictly in character):\n"
        f"{json.dumps(roster, ensure_ascii=False, indent=2)}\n\n"
        'Return ONLY JSON: {"verdicts": [{"key": <persona key>, "stance": "bullish|neutral|bearish", '
        '"score": <0-10 conviction within THAT master\'s framework>, '
        '"rationale": <one concise Chinese sentence in that master\'s voice>}, ...]} '
        "— exactly one entry per master, key must match the roster."
    )
    system = with_chinese(
        "You are LU's investment-council moderator, voicing each master faithfully and "
        "adversarially — they should genuinely disagree where their styles diverge. JSON only."
    )
    raw = provider.generate_json(prompt, system=system)
    usage.record(provider, "council", symbol)
    result = _build_council(raw)
    # Log the sized decision (with price-at-decision) for later reflection/grading.
    from .reflection import log_decision
    log_decision(symbol, kind="council", action=result.recommendation.action,
                 stance=result.consensus, score=result.avg_score,
                 price=bundle.quote.price, provider=provider.name)
    return _persist_council(symbol, result, provider.name)


def _persist_council(symbol: str, result: CouncilResult, provider: str) -> SavedCouncil:
    sym = symbol.upper()
    idem = dt.date.today().isoformat()  # one council per symbol per day
    with session_scope() as s:
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == sym, Analysis.kind == "council", Analysis.idempotency_key == idem,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=sym, kind="council", idempotency_key=idem)
            s.add(existing)
        existing.summary = f"{result.consensus} · 多 {result.bullish}/中 {result.neutral}/空 {result.bearish}"
        existing.structured_json = result.model_dump_json()
        existing.provider = provider
        s.flush()
        return SavedCouncil(symbol=sym, provider=provider, created_at=existing.created_at, result=result)


def latest_council(symbol: str) -> SavedCouncil | None:
    with session_scope() as s:
        row = s.execute(
            select(Analysis).where(Analysis.symbol == symbol.upper(), Analysis.kind == "council")
            .order_by(Analysis.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        return SavedCouncil(
            symbol=row.symbol, provider=row.provider, created_at=row.created_at,
            result=CouncilResult.model_validate_json(row.structured_json),
        )
