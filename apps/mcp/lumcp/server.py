"""LU MCP server (FastMCP).

The dual-brain seam. Read tools return deterministic facts computed by lucore;
the write-back tool persists the calling LLM's own structured opinion into the local DB.
Usable from Claude Desktop/Code/Cursor and from the headless `claude -p` brain.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lucore import __version__
from lucore.config import get_settings
from lucore.data.router import get_router
from lucore.db import init_db
from lucore.markets import infer_market
from lucore.services import portfolio as pf
from lucore.services.analyze import AnalysisResult, persist_analysis
from lucore.services.research import build_research_bundle, get_technical

mcp = FastMCP("limit-up")


@mcp.tool()
def lu_health() -> dict:
    """LU server status (version, db path, llm provider)."""
    s = get_settings()
    return {"status": "ok", "version": __version__, "db": str(s.db_path), "llm_provider": s.llm_provider}


@mcp.tool()
def search_stock(query: str) -> dict:
    """Resolve a ticker and return a quick quote (symbol, name, market, price, currency)."""
    symbol = query.strip().upper()
    q = get_router().get_quote(symbol)
    f = get_router().get_fundamentals(symbol)
    return {
        "symbol": symbol, "market": infer_market(symbol).value,
        "name": f.name, "price": q.price, "currency": q.currency,
    }


@mcp.tool()
def get_research_facts(symbol: str) -> dict:
    """Deterministic facts bundle for a symbol (quote, fundamentals, technical summary, news).
    Reason over THESE facts — do not invent numbers — then call save_analysis to persist your view."""
    return build_research_bundle(symbol.strip().upper()).model_dump(mode="json")


@mcp.tool()
def technical_analysis(symbol: str) -> dict:
    """Technical summary for a symbol: trend, signals, and latest indicator values (RSI/MACD/MAs/ATR)."""
    ta = get_technical(symbol.strip().upper())
    return {"trend": ta.trend, "signals": ta.signals, "latest": ta.latest}


@mcp.tool()
def save_analysis(
    symbol: str,
    summary: str,
    recommendation: str,
    score: float,
    bull_case: str = "",
    bear_case: str = "",
    risks: list[str] | None = None,
    catalysts: list[str] | None = None,
    target_price: float | None = None,
    time_horizon: str | None = None,
) -> dict:
    """Write-back: persist YOUR structured analysis of `symbol` into LU so the web app shows it.
    recommendation ∈ {Strong Buy, Buy, Hold, Sell, Strong Sell}; score 0-10 = conviction to buy now."""
    result = AnalysisResult(
        summary=summary, recommendation=recommendation, score=score,
        bull_case=bull_case, bear_case=bear_case,
        risks=risks or [], catalysts=catalysts or [],
        target_price=target_price, time_horizon=time_horizon,
    )
    saved = persist_analysis(symbol.strip().upper(), result, provider="mcp")
    return {"saved": True, "id": saved.id, "symbol": saved.symbol}


@mcp.tool()
def portfolio_analysis(portfolio_id: int = 0) -> dict:
    """Deterministic portfolio analytics (value, P&L, allocation, concentration, correlation).
    portfolio_id=0 -> the default portfolio. Reason over these facts, then optionally save a review."""
    pid = portfolio_id or pf.ensure_default_portfolio()
    return pf.get_analytics(pid).model_dump(mode="json")


def main() -> None:
    init_db()
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
