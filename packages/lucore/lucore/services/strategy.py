"""Strategy builder + backtest service (#9).

Pulls cached OHLCV, runs the deterministic backtester, and (optionally) has the LLM
narrate the result. The numbers are 100% compute; the AI only explains them.
"""
from __future__ import annotations

import json

from pydantic import BaseModel

from ..compute.backtest import BacktestResult, StrategySpec, backtest
from ..data.router import get_router
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage


class StrategyRead(BaseModel):
    summary: str
    verdict: str = ""  # robust | mixed | weak
    observations: list[str] = []
    cautions: list[str] = []


def run_backtest(symbol: str, spec: StrategySpec, *, period: str = "3y") -> BacktestResult:
    bars = get_router().get_ohlcv(symbol.upper(), period=period, interval="1d")
    if not bars:
        raise ValueError(f"no price history for {symbol}")
    return backtest(symbol, bars, spec)


def explain(result: BacktestResult, *, provider: LLMProvider | None = None) -> StrategyRead:
    provider = provider or get_provider()
    facts = {
        "symbol": result.symbol, "strategy": result.kind, "params": result.spec.model_dump(),
        "stats": result.stats.model_dump(), "num_trades": result.stats.trades,
    }
    spec = {
        "summary": "2-3 sentence read of how this strategy performed on this symbol",
        "verdict": "robust | mixed | weak",
        "observations": ["what the stats show (vs buy & hold, drawdown, win rate, exposure)"],
        "cautions": ["overfitting / sample-size / regime caveats"],
    }
    prompt = (
        "Interpret this deterministic backtest. Use ONLY these computed stats — do not invent "
        f"numbers.\nRESULT:\n{json.dumps(facts, indent=2, default=str)}\n\n"
        f"Return ONLY JSON:\n{json.dumps(spec, indent=2)}"
    )
    system = with_chinese(
        "You are LU's quant analyst. Judge the strategy honestly, flag overfitting and small samples. "
        "JSON only."
    )
    read = StrategyRead.model_validate(provider.generate_json(prompt, system=system))
    usage.record(provider, "backtest", result.symbol)
    return read
