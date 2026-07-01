"""Deterministic position sizing — the "portfolio-manager" step that turns a council vote
tally + conviction into an actionable, risk-capped suggested position. Computed in Python so
the recommendation is reproducible and auditable; the LLM only narrates it, never sizes it.

This mirrors the ai-hedge-fund risk-manager → portfolio-manager pipeline: the analysts (the
persona council) each vote; this function aggregates conviction and directional agreement into
a single suggested action + weight, capped at a prudent single-position limit.
"""
from __future__ import annotations

from pydantic import BaseModel

MAX_WEIGHT_PCT = 10.0  # prudent single-position cap


class PositionSuggestion(BaseModel):
    action: str = "hold"          # buy | add | hold | trim | sell
    label: str = "观望"            # Chinese display label
    target_weight_pct: float = 0.0  # suggested single-position weight (0 for hold/exit)
    conviction: float = 0.0        # 0..1 (from avg conviction score)
    directional: float = 0.0       # -1..1 net bull−bear agreement
    note: str = ""


def suggest_position(bullish: int, neutral: int, bearish: int, avg_score: float) -> PositionSuggestion:
    """Map a council tally to a sized action.

    directional = (bull−bear)/total agreement; conviction = avg_score/10. A long position is
    sized ∝ directional × conviction, capped at MAX_WEIGHT_PCT. Net-bearish agreement suggests
    trimming/exiting (weight 0); weak agreement → hold.
    """
    total = bullish + neutral + bearish
    if total == 0:
        return PositionSuggestion(note="无有效评审")

    directional = (bullish - bearish) / total          # -1..1
    conviction = max(0.0, min(1.0, avg_score / 10.0))    # 0..1

    # Net-bearish agreement → trim/exit (no long weight), sized by how negative it is.
    if directional <= -0.5:
        action, label, target = "sell", "卖出 / 回避", 0.0
    elif directional <= -0.2:
        action, label, target = "trim", "减仓", 0.0
    else:
        # One continuous long size drives BOTH the weight and the action tier, so the label is
        # always monotonic with the weight (a bigger position never gets a weaker label).
        target = round(max(0.0, directional) * conviction * MAX_WEIGHT_PCT, 1)
        if target >= 4.0:
            action, label = "buy", "买入(建仓)"
        elif target >= 1.0:
            action, label = "add", "小仓参与"
        else:
            action, label, target = "hold", "观望", 0.0

    note = f"方向 {directional:+.2f} · 信念 {conviction:.0%} · 单仓上限 {MAX_WEIGHT_PCT:.0f}%"
    return PositionSuggestion(
        action=action, label=label, target_weight_pct=target,
        conviction=round(conviction, 2), directional=round(directional, 2), note=note,
    )
