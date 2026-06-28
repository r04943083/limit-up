"""Stock research + technical + AI analysis routes (thin over lucore services)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.compute.indicators import TechnicalAnalysis
from lucore.data.base import Bar, Quote
from lucore.data.router import get_router
from lucore.services.analyze import SavedAnalysis, analyze_stock, latest_analysis
from lucore.services.news import SavedNewsAnalysis, analyze_news, latest_news_analysis
from lucore.services.research import ResearchBundle, get_research, get_technical
from lucore.services.sync import SyncResult, sync_symbol

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{symbol}/quote", response_model=Quote)
def quote(symbol: str) -> Quote:
    return get_router().get_quote(symbol.upper())


@router.get("/{symbol}/research", response_model=ResearchBundle)
def research(symbol: str, cached: bool = True) -> ResearchBundle:
    """Cached-first by default (loads the stored snapshot, fast). cached=false forces a live refresh."""
    try:
        return get_research(symbol.upper(), cached=cached)
    except Exception as e:  # noqa: BLE001 - surface data errors to the UI
        raise HTTPException(status_code=502, detail=f"data error: {e}") from e


@router.post("/{symbol}/sync", response_model=SyncResult)
def sync_one(symbol: str) -> SyncResult:
    """Pull latest live data for one symbol into the DB (snapshot + daily/weekly/monthly OHLCV)."""
    sym = symbol.upper()
    ok = sync_symbol(sym, warm=True)  # warm all chart timeframes — user is viewing this stock
    import datetime as dt
    return SyncResult(
        requested=1, synced=1 if ok else 0, failed=[] if ok else [sym],
        synced_at=dt.datetime.now(dt.timezone.utc),
    )


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


@router.post("/{symbol}/news-analysis", response_model=SavedNewsAnalysis)
def run_news_analysis(symbol: str) -> SavedNewsAnalysis:
    """AI sentiment over recent headlines (claude -p). Synchronous — may take ~20-40s."""
    try:
        return analyze_news(symbol.upper())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"news analysis failed: {e}") from e


@router.get("/{symbol}/news-analysis", response_model=SavedNewsAnalysis | None)
def get_news_analysis(symbol: str) -> SavedNewsAnalysis | None:
    return latest_news_analysis(symbol.upper())
