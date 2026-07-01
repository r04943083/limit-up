"""Cache-first SEC EDGAR feeds: insider transactions (Form 4) + recent filings.

US-only. Filings/insider data change slowly, so these use a per-day cache (fresh within the
same day). Non-US symbols return empty results without hitting the network. A failed fetch
degrades to ``ok=False`` (serving a prior cached report if one exists) so the UI never breaks.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..data import edgar as ed
from ..markets import Market, infer_market
from . import market_cache as mc

# Insider/filings move at most daily; a same-day cache is plenty and keeps the page instant.
_TTL_MIN = 12 * 60


class InsiderResult(BaseModel):
    ok: bool = True
    error: str | None = None
    report: ed.InsiderReport


class FilingsResult(BaseModel):
    ok: bool = True
    error: str | None = None
    filings: list[ed.FilingRow] = []


class _FilingsCache(BaseModel):
    filings: list[ed.FilingRow] = []


def _is_us(symbol: str) -> bool:
    return infer_market(symbol) == Market.US


def get_insider_report(symbol: str) -> InsiderResult:
    sym = symbol.upper()
    if not _is_us(sym):
        return InsiderResult(ok=True, report=ed.InsiderReport(symbol=sym))
    # Keyless of date (unlike cn per-trading-day caches): we always want the *latest* insider
    # picture, and a date-scoped key would hide yesterday's good cache from the stale-on-failure
    # fallback at the day boundary — exactly when an outage is most visible.
    key = f"insiders:{sym}"
    cached, fetched = mc.read(key)
    if cached and mc.fresh_enough(fetched, is_today=True, today_ttl_min=_TTL_MIN):
        return InsiderResult(report=ed.InsiderReport.model_validate_json(cached))
    try:
        report = ed.fetch_insider_report(sym)
        mc.write(key, report.model_dump_json())
        return InsiderResult(report=report)
    except Exception as e:  # noqa: BLE001
        if cached:
            return InsiderResult(ok=False, error=str(e),
                                 report=ed.InsiderReport.model_validate_json(cached))
        return InsiderResult(ok=False, error=str(e), report=ed.InsiderReport(symbol=sym))


def get_filings(symbol: str) -> FilingsResult:
    sym = symbol.upper()
    if not _is_us(sym):
        return FilingsResult(ok=True, filings=[])
    key = f"filings:{sym}"  # latest filings; date-independent (see get_insider_report)
    cached, fetched = mc.read(key)
    if cached and mc.fresh_enough(fetched, is_today=True, today_ttl_min=_TTL_MIN):
        return FilingsResult(filings=_FilingsCache.model_validate_json(cached).filings)
    try:
        rows = ed.fetch_recent_filings(sym)
        mc.write(key, _FilingsCache(filings=rows).model_dump_json())
        return FilingsResult(filings=rows)
    except Exception as e:  # noqa: BLE001
        if cached:
            return FilingsResult(ok=False, error=str(e),
                                 filings=_FilingsCache.model_validate_json(cached).filings)
        return FilingsResult(ok=False, error=str(e), filings=[])
