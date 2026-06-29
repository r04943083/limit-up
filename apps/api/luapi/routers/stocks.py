"""Stock research + technical + AI analysis routes (thin over lucore services)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.compute.indicators import TechnicalAnalysis
from lucore.data.base import Bar, CompanyProfile, Financials, Quote
from lucore.data.router import get_router
from lucore.services.analyze import SavedAnalysis, analyze_stock, latest_analysis
from lucore.services.financials import DcfView, compute_dcf, get_financials_cached
from lucore.services.intraday import IntradayPoint, get_intraday
from lucore.services.profile import get_profile_cached
from lucore.services.news import SavedNewsAnalysis, analyze_news, latest_news_analysis
from lucore.services.research import ResearchBundle, get_research, get_technical
from lucore.services.search import SymbolHit, search_symbols
from lucore.services.sync import SyncResult, sync_symbol
from lucore.services.valuation import ValuationOut, get_valuation

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/search", response_model=list[SymbolHit])
def search(q: str = "", limit: int = 20) -> list[SymbolHit]:
    """Autocomplete the global search box: match downloaded symbols by ticker + name."""
    return search_symbols(q, limit=limit)


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
    try:
        bars = get_router().get_ohlcv(symbol.upper(), period=period, interval=interval)
    except Exception as e:  # noqa: BLE001 - unknown ticker → 404, not a 500 spew
        raise HTTPException(status_code=404, detail=f"no price data: {e}") from e
    if not bars:
        raise HTTPException(status_code=404, detail="no price data")
    return bars


@router.get("/{symbol}/intraday", response_model=list[IntradayPoint])
def intraday(symbol: str, range: str = "1d") -> list[IntradayPoint]:
    """分时(1d/1m)或 5 日(5d/5m)。Live, not cached — intraday has many bars per day."""
    return get_intraday(symbol.upper(), range)


@router.get("/{symbol}/technical", response_model=TechnicalAnalysis)
def technical(symbol: str, period: str = "1y", interval: str = "1d") -> TechnicalAnalysis:
    try:
        ta = get_technical(symbol.upper(), period=period, interval=interval)
    except Exception as e:  # noqa: BLE001 - unknown ticker → 404, not a 500 spew
        raise HTTPException(status_code=404, detail=f"no price data: {e}") from e
    if not ta.dates:
        raise HTTPException(status_code=404, detail="no price data")
    return ta


@router.get("/{symbol}/financials", response_model=Financials)
def financials(symbol: str) -> Financials:
    """Curated financial statements (annual + quarterly), cache-first (~weekly refresh)."""
    return get_financials_cached(symbol.upper())


@router.get("/{symbol}/profile", response_model=CompanyProfile)
def profile(symbol: str) -> CompanyProfile:
    """Company overview + dividend history + ownership, cache-first (~weekly refresh)."""
    return get_profile_cached(symbol.upper())


@router.get("/{symbol}/valuation", response_model=ValuationOut)
def valuation(symbol: str) -> ValuationOut:
    """Futu-style 历史估值带 (PE/PB/PS bands + 平均/分位) + analyst consensus.
    Rebuilt deterministically from cached daily closes ÷ reported quarterly per-share figures."""
    return get_valuation(symbol.upper())


@router.get("/{symbol}/dcf", response_model=DcfView)
def dcf_view(
    symbol: str,
    growth: float | None = None,
    discount: float | None = None,
    terminal: float | None = None,
    years: int | None = None,
) -> DcfView:
    """Two-stage DCF intrinsic value. Omit params to use sensible defaults (growth from FCF CAGR)."""
    return compute_dcf(symbol.upper(), growth=growth, discount=discount,
                       terminal_growth=terminal, years=years)


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
