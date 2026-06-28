"""Portfolio service: CSV import, analytics assembly, and AI review write-back."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json

from pydantic import BaseModel
from sqlalchemy import select

from ..compute.portfolio import (
    PortfolioAnalytics,
    PositionInput,
    compute_correlation,
    compute_portfolio,
    returns_from_closes,
)
from ..data.cache import ensure_stock
from ..data.fx import fx_map
from ..data.router import get_router
from ..db import session_scope
from ..db.models import Analysis, Holding, Portfolio, Stock
from ..llm.base import LLMProvider, get_provider, with_chinese
from ..markets import MARKET_CURRENCY, infer_market
from . import usage

# CSV header aliases (covers Futu / IBKR / generic exports).
_SYM = {"symbol", "ticker", "code", "代码", "证券代码", "stock"}
_QTY = {"quantity", "qty", "shares", "数量", "持仓数量", "position"}
_COST = {"avg_cost", "cost", "avgcost", "average cost", "avg price", "cost price", "成本价", "成本"}


class HoldingOut(BaseModel):
    id: int
    symbol: str
    market: str
    name: str | None
    quantity: float
    avg_cost: float | None
    source: str | None


class PortfolioReview(BaseModel):
    summary: str
    strengths: list[str] = []
    concerns: list[str] = []
    suggestions: list[str] = []
    risk_level: str = "medium"
    diversification: str = ""


def ensure_default_portfolio() -> int:
    with session_scope() as s:
        p = s.execute(select(Portfolio).order_by(Portfolio.id).limit(1)).scalar_one_or_none()
        if p:
            return p.id
        p = Portfolio(name="My Portfolio")
        s.add(p)
        s.flush()
        return p.id


def list_holdings(portfolio_id: int) -> list[HoldingOut]:
    with session_scope() as s:
        rows = s.execute(
            select(Holding).where(Holding.portfolio_id == portfolio_id).order_by(Holding.symbol)
        ).scalars().all()
        out = []
        for h in rows:
            stock = s.get(Stock, h.symbol)
            out.append(
                HoldingOut(
                    id=h.id, symbol=h.symbol, market=stock.market if stock else infer_market(h.symbol).value,
                    name=stock.name if stock else None, quantity=h.quantity, avg_cost=h.avg_cost, source=h.source,
                )
            )
        return out


def upsert_holding(
    portfolio_id: int, symbol: str, quantity: float, avg_cost: float | None, source: str = "manual"
) -> None:
    symbol = symbol.strip().upper()
    if not symbol:
        return
    ensure_stock(symbol)
    with session_scope() as s:
        h = s.execute(
            select(Holding).where(Holding.portfolio_id == portfolio_id, Holding.symbol == symbol)
        ).scalar_one_or_none()
        if h is None:
            s.add(Holding(portfolio_id=portfolio_id, symbol=symbol, quantity=quantity, avg_cost=avg_cost, source=source))
        else:
            h.quantity = quantity
            if avg_cost is not None:
                h.avg_cost = avg_cost
            h.source = source


def remove_holding(holding_id: int) -> bool:
    with session_scope() as s:
        h = s.get(Holding, holding_id)
        if h is None:
            return False
        s.delete(h)
        return True


def _num(v: str) -> float | None:
    try:
        return float(v.replace(",", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return None


def import_csv(portfolio_id: int, csv_text: str) -> int:
    rows = [r for r in csv.reader(io.StringIO(csv_text)) if r]
    if not rows:
        return 0
    header = [h.strip().lower() for h in rows[0]]
    sym_i = next((i for i, h in enumerate(header) if h in _SYM), None)
    if sym_i is None:
        return 0  # need a symbol column for holdings import
    qty_i = next((i for i, h in enumerate(header) if h in _QTY), None)
    cost_i = next((i for i, h in enumerate(header) if h in _COST), None)
    added = 0
    for r in rows[1:]:
        if sym_i >= len(r):
            continue
        sym = r[sym_i].strip().upper()
        if not sym:
            continue
        qty = _num(r[qty_i]) if qty_i is not None and qty_i < len(r) else None
        cost = _num(r[cost_i]) if cost_i is not None and cost_i < len(r) else None
        upsert_holding(portfolio_id, sym, qty or 0.0, cost, source="csv")
        added += 1
    return added


def get_analytics(portfolio_id: int, base_currency: str = "USD") -> PortfolioAnalytics:
    router = get_router()
    holdings = list_holdings(portfolio_id)
    inputs: list[PositionInput] = []
    returns_by_symbol: dict[str, list[float]] = {}
    currencies: set[str] = {base_currency}

    for h in holdings:
        market = infer_market(h.symbol)
        f = router.get_fundamentals(h.symbol)
        bars = router.get_ohlcv(h.symbol, period="6mo")
        price = bars[-1].close if bars else None
        currency = f.currency or MARKET_CURRENCY.get(market, "USD")
        currencies.add(currency)
        inputs.append(
            PositionInput(
                symbol=h.symbol, market=market.value, quantity=h.quantity, avg_cost=h.avg_cost,
                price=price, currency=currency, sector=f.sector, name=f.name or h.name,
            )
        )
        if len(bars) >= 2:
            returns_by_symbol[h.symbol] = returns_from_closes([b.close for b in bars[-120:]])

    analytics = compute_portfolio(inputs, fx_map(currencies, base_currency), base_currency)
    syms, matrix = compute_correlation(returns_by_symbol)
    analytics.correlation_symbols = syms
    analytics.correlation_matrix = matrix
    return analytics


def _review_facts(a: PortfolioAnalytics) -> dict:
    return {
        "base_currency": a.base_currency,
        "total_value": round(a.total_value, 2),
        "total_pnl_pct": round(a.total_pnl_pct, 2) if a.total_pnl_pct is not None else None,
        "positions": [
            {"symbol": p.symbol, "weight_pct": round(p.weight * 100, 1), "pnl_pct": round(p.pnl_pct, 1) if p.pnl_pct is not None else None, "sector": p.sector}
            for p in a.positions
        ],
        "sector_allocation_pct": {k: round(v * 100, 1) for k, v in a.sector_alloc.items()},
        "market_allocation_pct": {k: round(v * 100, 1) for k, v in a.market_alloc.items()},
        "top_position_weight_pct": round(a.top_weight * 100, 1),
        "concentration_hhi": round(a.hhi, 3),
    }


def review_portfolio(portfolio_id: int, *, provider: LLMProvider | None = None) -> PortfolioReview:
    analytics = get_analytics(portfolio_id)
    provider = provider or get_provider()
    spec = {
        "summary": "2-4 sentences on the portfolio's posture",
        "strengths": ["bullets"], "concerns": ["bullets, e.g. concentration/sector tilt/correlation"],
        "suggestions": ["actionable bullets"], "risk_level": "low | medium | high",
        "diversification": "one sentence on diversification quality",
    }
    prompt = (
        "Review this portfolio. FACTS (ground truth):\n"
        f"{json.dumps(_review_facts(analytics), indent=2)}\n\n"
        f"Return ONLY JSON with keys:\n{json.dumps(spec, indent=2)}"
    )
    system = with_chinese(
        "You are LU's portfolio risk reviewer. Reason over the provided facts only; never invent "
        "numbers. Focus on concentration, sector/market tilts, correlation and risk. JSON only."
    )
    review = PortfolioReview.model_validate(provider.generate_json(prompt, system=system))
    usage.record(provider, "portfolio", f"@PORTFOLIO:{portfolio_id}")

    idem = dt.date.today().isoformat()
    with session_scope() as s:
        key = f"@PORTFOLIO:{portfolio_id}"
        existing = s.execute(
            select(Analysis).where(
                Analysis.symbol == key, Analysis.kind == "portfolio", Analysis.idempotency_key == idem
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Analysis(symbol=key, kind="portfolio", idempotency_key=idem)
            s.add(existing)
        existing.summary = review.summary
        existing.structured_json = review.model_dump_json()
        existing.provider = provider.name
    return review


def latest_review(portfolio_id: int) -> PortfolioReview | None:
    with session_scope() as s:
        row = s.execute(
            select(Analysis)
            .where(Analysis.symbol == f"@PORTFOLIO:{portfolio_id}", Analysis.kind == "portfolio")
            .order_by(Analysis.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None or not row.structured_json:
            return None
        return PortfolioReview.model_validate_json(row.structured_json)
