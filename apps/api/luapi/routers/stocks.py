"""Stock research + technical + AI analysis routes (thin over lucore services)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.compute.indicators import TechnicalAnalysis
from lucore.data.base import Bar, Quote
from lucore.data.router import get_router
from lucore.services.analyze import SavedAnalysis, analyze_stock, latest_analysis
from lucore.services.research import ResearchBundle, build_research_bundle, get_technical

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{symbol}/quote", response_model=Quote)
def quote(symbol: str) -> Quote:
    return get_router().get_quote(symbol.upper())


@router.get("/{symbol}/research", response_model=ResearchBundle)
def research(symbol: str) -> ResearchBundle:
    try:
        return build_research_bundle(symbol.upper())
    except Exception as e:  # noqa: BLE001 - surface data errors to the UI
        raise HTTPException(status_code=502, detail=f"data error: {e}") from e


@router.get("/{symbol}/ohlcv", response_model=list[Bar])
def ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> list[Bar]:
    bars = get_router().get_ohlcv(symbol.upper(), period=period, interval=interval)
    if not bars:
        raise HTTPException(status_code=404, detail="no price data")
    return bars


@router.get("/{symbol}/technical", response_model=TechnicalAnalysis)
def technical(symbol: str, period: str = "1y", interval: str = "1d") -> TechnicalAnalysis:
    ta = get_technical(symbol.upper(), period=period, interval=interval)
    if not ta.dates:
        raise HTTPException(status_code=404, detail="no price data")
    return ta


@router.post("/{symbol}/analyze", response_model=SavedAnalysis)
def analyze(symbol: str) -> SavedAnalysis:
    """Run the AI brain (claude -p by default). Synchronous — may take ~30-60s."""
    try:
        return analyze_stock(symbol.upper())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"analysis failed: {e}") from e


@router.get("/{symbol}/analysis", response_model=SavedAnalysis | None)
def get_analysis(symbol: str) -> SavedAnalysis | None:
    return latest_analysis(symbol.upper())
