"""Cache-first SEC EDGAR feeds: insider transactions (Form 4) + recent filings.

US-only. Filings/insider data change slowly, so these use a per-day cache (fresh within the
same day). Non-US symbols return empty results without hitting the network. A failed fetch
degrades to ``ok=False`` (serving a prior cached report if one exists) so the UI never breaks.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..compute.textdiff import TextDiff, diff_text
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


class FilingDiffResult(BaseModel):
    ok: bool = True
    error: str | None = None
    symbol: str
    form: str = "10-K"
    section: str = "risk_factors"
    section_label: str = ""
    old_date: str | None = None
    new_date: str | None = None
    diff: TextDiff = TextDiff()


def get_filing_diff(symbol: str, *, form: str = "10-K", section: str = "risk_factors") -> FilingDiffResult:
    """Red-line diff of a narrative section (e.g. Risk Factors) between the two most recent
    filings of ``form``. US-only, cache-first (annual/quarterly filings change slowly)."""
    sym = symbol.upper()
    label = ed.SECTIONS.get(section, section)
    if section not in ed.SECTIONS:
        return FilingDiffResult(ok=False, error="unknown section", symbol=sym, form=form, section=section)
    if not _is_us(sym):
        return FilingDiffResult(ok=True, symbol=sym, form=form, section=section, section_label=label)
    key = f"filingdiff:{sym}:{form}:{section}"
    cached, fetched = mc.read(key)
    if cached and mc.fresh_enough(fetched, is_today=True, today_ttl_min=_TTL_MIN):
        return FilingDiffResult.model_validate_json(cached)
    try:
        secs = ed.fetch_sections(sym, form=form, section=section, n=2)
        if len(secs) < 2 or not secs[0].text or not secs[1].text:
            # Deterministic negative (this section won't diff today) — cache it so repeated
            # clicks don't re-parse two 10-Ks each time just to get the same "can't diff".
            degenerate = FilingDiffResult(ok=False, error="需要两期可解析的申报", symbol=sym,
                                          form=form, section=section, section_label=label)
            mc.write(key, degenerate.model_dump_json())
            return degenerate
        new, old = secs[0], secs[1]  # head() is newest-first
        res = FilingDiffResult(
            ok=True, symbol=sym, form=form, section=section, section_label=label,
            old_date=old.date, new_date=new.date, diff=diff_text(old.text, new.text),
        )
        mc.write(key, res.model_dump_json())
        return res
    except Exception as e:  # noqa: BLE001 - transient fetch error: serve stale but flag ok=False
        if cached:
            stale = FilingDiffResult.model_validate_json(cached)
            return stale.model_copy(update={"ok": False, "error": str(e)})
        return FilingDiffResult(ok=False, error=str(e), symbol=sym, form=form,
                                section=section, section_label=label)
