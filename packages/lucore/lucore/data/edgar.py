"""SEC EDGAR data via edgartools: insider transactions (Form 4) + recent filings.

US-only (EDGAR is a US regulator). Market-wide/per-company filings, not quote data, so like
the movers feeds this lives outside MarketDataAdapter. Every number is parsed straight from
the filing — the LLM never invents any of it.

SEC requires a declared identity (User-Agent); we set it once from settings. Network fetches
are relatively slow (~0.7s per Form 4), so callers cache aggressively (see services/edgar_svc).
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from ..config import get_settings

_identity_set = False


def _ensure_identity() -> None:
    global _identity_set
    if not _identity_set:
        import edgar

        edgar.set_identity(get_settings().sec_user_agent)
        _identity_set = True


# Form 4 transaction codes worth surfacing as sentiment. P = open-market/private purchase
# (bullish), S = sale (bearish); the rest (grants/exercises/tax) are compensation noise.
_BUY_CODE = "P"
_SELL_CODE = "S"


class InsiderTx(BaseModel):
    date: str | None = None          # transaction date (YYYY-MM-DD)
    insider: str | None = None
    position: str | None = None       # role, e.g. "CFO", "10% owner", "Director"
    code: str | None = None           # SEC transaction code (P/S/A/M/F/G…)
    type: str | None = None           # human label from edgartools (purchase/sale/…)
    shares: float | None = None
    price: float | None = None
    value: float | None = None
    security: str | None = None       # security title


class InsiderReport(BaseModel):
    symbol: str
    window_days: int = 90
    transactions: list[InsiderTx] = []
    buy_count: int = 0                # open-market purchase transactions (code P)
    sell_count: int = 0              # open-market sale transactions (code S)
    distinct_buyers: int = 0
    distinct_sellers: int = 0
    net_shares: float | None = None   # Σ P shares − Σ S shares over the window
    cluster_buy: bool = False         # ≥2 distinct insiders bought on the open market — a signal


class FilingRow(BaseModel):
    form: str
    date: str | None = None           # filing date
    title: str | None = None
    url: str | None = None
    accession: str | None = None


def _num(v) -> float | None:  # noqa: ANN001
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def fetch_insider_report(symbol: str, *, filings: int = 20, window_days: int = 90) -> InsiderReport:
    """Parse the most recent Form 4 filings into transactions + a cluster-buy signal.

    ``filings`` bounds how many recent Form 4s we fetch (each is a network round-trip);
    ``window_days`` bounds the recency window used for the buy/sell tallies + cluster signal.
    """
    _ensure_identity()
    import edgar

    company = edgar.Company(symbol.upper())
    recent = company.get_filings(form="4").head(filings)
    cutoff = dt.date.today() - dt.timedelta(days=window_days)

    txs: list[InsiderTx] = []
    buyers: set[str] = set()
    sellers: set[str] = set()
    buy_n = sell_n = 0
    net = 0.0
    for f in recent:
        try:
            obj = f.obj()
            acts = obj.get_transaction_activities()
        except Exception:  # noqa: BLE001 - one malformed filing shouldn't sink the report
            continue
        insider = getattr(obj, "insider_name", None)
        position = getattr(obj, "position", None)
        for a in acts:
            code = getattr(a, "code", None)
            shares = _num(getattr(a, "shares", None))
            row_date = _to_date_str(getattr(a, "transaction_date", None) or obj.reporting_period)
            txs.append(InsiderTx(
                date=row_date, insider=insider, position=position, code=code,
                type=getattr(a, "transaction_type", None), shares=shares,
                price=_num(getattr(a, "price_per_share", None)),
                value=_num(getattr(a, "value", None)),
                security=getattr(a, "security_title", None),
            ))
            # Tally open-market buys/sells within the recency window.
            in_window = _date_ge(row_date, cutoff)
            if code == _BUY_CODE and in_window:
                buy_n += 1
                if insider:
                    buyers.add(insider)
                if shares:
                    net += shares
            elif code == _SELL_CODE and in_window:
                sell_n += 1
                if insider:
                    sellers.add(insider)
                if shares:
                    net -= shares

    return InsiderReport(
        symbol=symbol.upper(), window_days=window_days,
        # Keep enough rows that the window tallies in the header reconcile with the table
        # (up to `filings` × a few activities each); a safety cap guards a pathological filer.
        transactions=txs[:200], buy_count=buy_n, sell_count=sell_n,
        distinct_buyers=len(buyers), distinct_sellers=len(sellers),
        net_shares=net if (buy_n or sell_n) else None,
        cluster_buy=len(buyers) >= 2,
    )


def fetch_recent_filings(symbol: str, *, limit: int = 15) -> list[FilingRow]:
    """Recent SEC filings (10-K/10-Q/8-K/4/…) for the company, newest first."""
    _ensure_identity()
    import edgar

    company = edgar.Company(symbol.upper())
    out: list[FilingRow] = []
    for f in company.get_filings().head(limit):
        out.append(FilingRow(
            form=str(getattr(f, "form", "") or ""),
            date=_to_date_str(getattr(f, "filing_date", None)),
            title=getattr(f, "primary_doc_description", None) or None,
            url=getattr(f, "filing_url", None) or getattr(f, "homepage_url", None),
            accession=str(getattr(f, "accession_no", "") or "") or None,
        ))
    return out


class FilingSection(BaseModel):
    date: str | None = None
    form: str
    text: str = ""


# Diff-able 10-K/10-Q narrative sections → Chinese label. Keys are edgartools TenK/TenQ attrs.
SECTIONS: dict[str, str] = {
    "risk_factors": "风险因素",
    "management_discussion": "管理层讨论 (MD&A)",
    "business": "业务概况",
}


def fetch_sections(symbol: str, *, form: str = "10-K", section: str = "risk_factors",
                   n: int = 2) -> list[FilingSection]:
    """The named narrative section from the ``n`` most recent filings of ``form`` (newest first)."""
    if section not in SECTIONS:
        raise ValueError(f"unknown section: {section}")
    _ensure_identity()
    import edgar

    company = edgar.Company(symbol.upper())
    out: list[FilingSection] = []
    for f in company.get_filings(form=form).head(n):
        text = ""
        try:
            val = getattr(f.obj(), section, None)
            text = str(val) if val else ""
        except Exception:  # noqa: BLE001 - a section that won't parse degrades to empty
            text = ""
        out.append(FilingSection(date=_to_date_str(getattr(f, "filing_date", None)),
                                 form=form, text=text))
    return out


def _to_date_str(v) -> str | None:  # noqa: ANN001
    if v is None:
        return None
    if isinstance(v, str):
        return v[:10]
    iso = getattr(v, "isoformat", None)
    return iso()[:10] if iso else str(v)[:10]


def _date_ge(date_str: str | None, cutoff: dt.date) -> bool:
    if not date_str:
        return False
    try:
        return dt.date.fromisoformat(date_str[:10]) >= cutoff
    except ValueError:
        return False
