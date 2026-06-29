"""Deterministic stock screener over cached research snapshots.

Every Snapshot bundle already carries a quote + a rich fundamentals block (sector/industry,
pe/pb/ps/peg/ev_ebitda, roe/roa, margins, revenue/earnings growth, market cap, 52-week
range, short interest, ...). The screener flattens those into numeric *metrics* and applies
min/max + categorical filters, then sorts. Pure compute — the LLM is never involved.

Units are normalised to what the UI shows: ratios as-is; fraction fields (roe/roa/margins/
growth/short) → percent; dividend yield is already percent from yfinance; market cap → 亿
(local currency, so cross-market cap filters are approximate). A stock with no snapshot is
not a candidate — seed the universe and sync first.
"""
from __future__ import annotations

import json

from pydantic import BaseModel
from sqlalchemy import select

from ..db import session_scope
from ..db.models import Snapshot


class FieldDef(BaseModel):
    key: str
    label: str
    group: str
    unit: str = ""
    better: str = ""  # "high" | "low" | "" — hint for the UI


# Field catalogue the UI renders filters from. `better` marks the "good" direction.
FIELDS: list[FieldDef] = [
    # 估值
    FieldDef(key="pe_ttm", label="市盈率TTM", group="估值", unit="x", better="low"),
    FieldDef(key="pe_fwd", label="预期市盈率", group="估值", unit="x", better="low"),
    FieldDef(key="pb", label="市净率", group="估值", unit="x", better="low"),
    FieldDef(key="ps", label="市销率", group="估值", unit="x", better="low"),
    FieldDef(key="peg", label="PEG", group="估值", unit="x", better="low"),
    FieldDef(key="ev_ebitda", label="EV/EBITDA", group="估值", unit="x", better="low"),
    FieldDef(key="dividend_yield", label="股息率", group="估值", unit="%", better="high"),
    # 行情
    FieldDef(key="market_cap", label="市值", group="行情", unit="亿", better="high"),
    FieldDef(key="price", label="现价", group="行情", unit=""),
    FieldDef(key="change_pct", label="涨跌幅", group="行情", unit="%"),
    FieldDef(key="week52_pos", label="52周位置", group="行情", unit="%"),
    FieldDef(key="beta", label="Beta", group="行情", unit=""),
    # 基本面增长
    FieldDef(key="roe", label="ROE", group="基本面", unit="%", better="high"),
    FieldDef(key="roa", label="ROA", group="基本面", unit="%", better="high"),
    FieldDef(key="gross_margin", label="毛利率", group="基本面", unit="%", better="high"),
    FieldDef(key="operating_margin", label="营业利润率", group="基本面", unit="%", better="high"),
    FieldDef(key="net_margin", label="净利率", group="基本面", unit="%", better="high"),
    FieldDef(key="revenue_growth", label="营收增速", group="基本面", unit="%", better="high"),
    FieldDef(key="earnings_growth", label="盈利增速", group="基本面", unit="%", better="high"),
    # 涨停 / 题材
    FieldDef(key="limit_up_boards", label="连板数(A股)", group="涨停题材", unit="板", better="high"),
    FieldDef(key="short_percent", label="卖空比例", group="涨停题材", unit="%", better="low"),
]
FIELD_KEYS = {f.key for f in FIELDS}

# Fraction (0.42) → percent (42). dividend_yield/change_pct are already percent.
_PCT_FRACTION = {
    "roe", "roa", "gross_margin", "operating_margin", "net_margin",
    "revenue_growth", "earnings_growth", "short_percent",
}


class Filter(BaseModel):
    field: str
    min: float | None = None
    max: float | None = None


class ScreenSpec(BaseModel):
    filters: list[Filter] = []
    markets: list[str] = []      # subset of US/HK/CN; empty = all
    sectors: list[str] = []      # match fundamentals.sector; empty = all
    limit_up_only: bool = False  # A-share: only stocks in today's limit-up pool
    sort_field: str = "market_cap"
    sort_desc: bool = True
    limit: int = 100


class ScreenHit(BaseModel):
    symbol: str
    name: str | None = None
    market: str | None = None
    sector: str | None = None
    industry: str | None = None
    metrics: dict[str, float | None]


class ScreenResult(BaseModel):
    universe: int          # snapshots considered
    matched: int           # rows passing all filters
    results: list[ScreenHit]
    sectors: list[str]     # distinct sectors present (UI facet)


def _num(v) -> float | None:  # noqa: ANN001
    try:
        if v is None:
            return None
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or x in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return x


def _metrics(bundle: dict, lu_boards: dict[str, int | None]) -> dict[str, float | None]:
    f = bundle.get("fundamentals") or {}
    q = bundle.get("quote") or {}
    price = _num(q.get("price"))
    hi, lo = _num(f.get("week52_high")), _num(f.get("week52_low"))
    pos = ((price - lo) / (hi - lo) * 100) if (price is not None and hi and lo and hi > lo) else None
    mc = _num(f.get("market_cap"))

    def pf(k: str) -> float | None:
        v = _num(f.get(k))
        return v * 100 if v is not None else None

    return {
        "pe_ttm": _num(f.get("pe_ttm")), "pe_fwd": _num(f.get("pe_fwd")),
        "pb": _num(f.get("pb")), "ps": _num(f.get("ps")), "peg": _num(f.get("peg")),
        "ev_ebitda": _num(f.get("ev_ebitda")), "dividend_yield": _num(f.get("dividend_yield")),
        "market_cap": (mc / 1e8 if mc is not None else None), "price": price,
        "change_pct": _num(q.get("change_pct")), "week52_pos": pos, "beta": _num(f.get("beta")),
        "roe": pf("roe"), "roa": pf("roa"), "gross_margin": pf("gross_margin"),
        "operating_margin": pf("operating_margin"), "net_margin": pf("net_margin"),
        "revenue_growth": pf("revenue_growth"), "earnings_growth": pf("earnings_growth"),
        "short_percent": pf("short_percent"),
        "limit_up_boards": (lambda b: float(b) if b is not None else None)(lu_boards.get(bundle.get("symbol", ""))),
    }


def _limit_up_boards() -> dict[str, int | None]:
    """A-share canonical symbol → 连板数 from today's cached limit-up pool. Empty on any error."""
    try:
        from ..data.universe import _cn_symbol
        from .cn_market import get_limit_up_pool

        pool = get_limit_up_pool().pool
        out: dict[str, int | None] = {}
        for st in pool.stocks:
            sym = _cn_symbol(st.code)
            if sym:
                out[sym] = st.boards
        return out
    except Exception:  # noqa: BLE001
        return {}


def run_screen(spec: ScreenSpec) -> ScreenResult:
    # The A-share limit-up pool is only needed when the user actually screens by 连板;
    # skip the (network) fetch otherwise so a US/value screen stays instant.
    needs_lu = (
        spec.limit_up_only
        or spec.sort_field == "limit_up_boards"
        or any(f.field == "limit_up_boards" for f in spec.filters)
    )
    lu = _limit_up_boards() if needs_lu else {}
    with session_scope() as s:
        rows = s.execute(select(Snapshot.symbol, Snapshot.bundle_json)).all()

    sectors: set[str] = set()
    candidates: list[tuple[str, str | None, str | None, str | None, str | None, dict]] = []
    for sym, bj in rows:
        try:
            b = json.loads(bj)
        except (TypeError, ValueError):
            continue
        f = b.get("fundamentals") or {}
        sec, ind = f.get("sector"), f.get("industry")
        if sec:
            sectors.add(sec)
        name = f.get("name") or (b.get("quote") or {}).get("name")
        candidates.append((sym, name, b.get("market"), sec, ind, _metrics(b, lu)))

    valid_filters = [fl for fl in spec.filters if fl.field in FIELD_KEYS and (fl.min is not None or fl.max is not None)]
    out: list[ScreenHit] = []
    for sym, name, market, sec, ind, m in candidates:
        if spec.markets and market not in spec.markets:
            continue
        if spec.sectors and sec not in spec.sectors:
            continue
        if spec.limit_up_only and m.get("limit_up_boards") is None:
            continue
        ok = True
        for fl in valid_filters:
            v = m.get(fl.field)
            if v is None or (fl.min is not None and v < fl.min) or (fl.max is not None and v > fl.max):
                ok = False
                break
        if ok:
            out.append(ScreenHit(symbol=sym, name=name, market=market, sector=sec, industry=ind, metrics=m))

    sf = spec.sort_field if spec.sort_field in FIELD_KEYS else "market_cap"
    present = [h for h in out if h.metrics.get(sf) is not None]
    absent = [h for h in out if h.metrics.get(sf) is None]
    present.sort(key=lambda h: h.metrics[sf], reverse=spec.sort_desc)
    ordered = present + absent
    return ScreenResult(
        universe=len(candidates),
        matched=len(ordered),
        results=ordered[: max(1, spec.limit)],
        sectors=sorted(sectors),
    )
