"""Import Futu (富途牛牛) ``.ebk`` watchlist exports.

A ``.ebk`` file is a flat, BOM-prefixed, CRLF list of Futu-coded tickers — one per line.
It does NOT carry group names (the ``LIST####`` tokens are references to Futu's internal
custom-list objects, not group separators). So to preserve groups the user exports each
Futu group separately (filename = group name); :func:`import_ebk_files` then creates one
LU watchlist per file.

Line encodings observed:
  ``31#NVDA``      US equity           -> ``NVDA``
  ``31#BRK.B``     US class share      -> ``BRK-B`` (yfinance style)
  ``74#00700``     HK equity           -> ``0700.HK``
  ``1688347``      A-share Shanghai    -> ``688347.SS``
  ``0002645``      A-share Shenzhen    -> ``002645.SZ``
Non-equity entries are recognised and skipped: indices (``31#.SPX``), futures
(``31#ESmain``), bonds (``BD#...``), AU/SG/forex (``AU#``/``SG#``/``2USDindex``),
A-share indices (``1000001`` = 上证指数), and Futu list refs (``LIST####``).
"""
from __future__ import annotations

from pydantic import BaseModel

from ..markets import Market
from .watchlist import add_item, create_watchlist, get_watchlist, list_watchlists


class ParsedSymbol(BaseModel):
    raw: str
    symbol: str | None = None  # normalized LU symbol when it is a supported equity
    market: str | None = None
    kind: str = "equity"  # equity | index | future | bond | list | foreign | unknown
    skipped_reason: str | None = None


def _parse_line(raw: str) -> ParsedSymbol:
    line = raw.strip().lstrip("﻿")
    if not line:
        return ParsedSymbol(raw=raw, kind="unknown", skipped_reason="empty")
    if "LIST" in line:
        return ParsedSymbol(raw=line, kind="list", skipped_reason="Futu 列表引用")

    if "#" in line:
        prefix, rest = line.split("#", 1)
        rest = rest.strip()
        if rest.startswith("."):
            return ParsedSymbol(raw=line, kind="index", skipped_reason="指数")
        if rest.endswith("main"):
            return ParsedSymbol(raw=line, kind="future", skipped_reason="期货")
        if prefix == "31":  # US
            sym = rest.replace(".", "-")  # BRK.B -> BRK-B
            return ParsedSymbol(raw=line, symbol=sym, market=Market.US.value, kind="equity")
        if prefix == "74":  # HK
            if rest.isdigit() and len(rest) <= 5:
                return ParsedSymbol(
                    raw=line, symbol=f"{int(rest):04d}.HK", market=Market.HK.value, kind="equity"
                )
            return ParsedSymbol(raw=line, kind="index", skipped_reason="港股指数/非个股")
        if prefix == "BD":
            return ParsedSymbol(raw=line, kind="bond", skipped_reason="债券")
        if prefix in ("AU", "SG"):
            return ParsedSymbol(raw=line, kind="foreign", skipped_reason="暂不支持的市场")
        return ParsedSymbol(raw=line, kind="unknown", skipped_reason="未知编码")

    # Bare numeric -> A-share (market digit + 6-digit code).
    if line.isdigit() and len(line) == 7:
        mkt, code = line[0], line[1:]
        if mkt == "1":  # Shanghai
            if code.startswith("000"):
                return ParsedSymbol(raw=line, kind="index", skipped_reason="A股指数")
            return ParsedSymbol(raw=line, symbol=f"{code}.SS", market=Market.CN.value, kind="equity")
        if mkt == "0":  # Shenzhen
            return ParsedSymbol(raw=line, symbol=f"{code}.SZ", market=Market.CN.value, kind="equity")
    if line.startswith("2"):  # e.g. 2USDindex
        return ParsedSymbol(raw=line, kind="foreign", skipped_reason="外汇/指数")
    return ParsedSymbol(raw=line, kind="unknown", skipped_reason="未识别")


def parse_ebk(text: str) -> list[ParsedSymbol]:
    return [_parse_line(ln) for ln in text.splitlines() if ln.strip()]


def to_futu_line(symbol: str) -> str | None:
    """Reverse of :func:`_parse_line` — turn an LU symbol back into a Futu ``.ebk`` code.

    ``NVDA``->``31#NVDA`` · ``BRK-B``->``31#BRK.B`` · ``0700.HK``->``74#00700`` ·
    ``600519.SS``->``1600519`` · ``002645.SZ``->``0002645``. Returns None if unmappable.
    """
    sym = symbol.strip().upper()
    if not sym:
        return None
    if sym.endswith(".HK"):
        code = sym[:-3]
        return f"74#{int(code):05d}" if code.isdigit() else None
    if sym.endswith(".SS"):
        code = sym[:-3]
        return f"1{code}" if code.isdigit() else None
    if sym.endswith(".SZ"):
        code = sym[:-3]
        return f"0{code}" if code.isdigit() else None
    # Default: US equity (BRK-B -> BRK.B).
    return f"31#{sym.replace('-', '.')}"


class EbkExport(BaseModel):
    filename: str
    content: str
    count: int


def export_watchlist_ebk(watchlist_id: int) -> EbkExport | None:
    """Serialize a watchlist group to Futu ``.ebk`` text (BOM + CRLF), re-importable by Futu."""
    from .watchlist import get_watchlist

    wl = get_watchlist(watchlist_id)
    if wl is None:
        return None
    lines = [ln for it in wl.items if (ln := to_futu_line(it.symbol))]
    # BOM + CRLF newlines is what Futu writes (and what parse_ebk tolerates on re-import).
    content = "﻿" + "".join(f"{ln}\r\n" for ln in lines)
    return EbkExport(filename=f"{wl.name}.ebk", content=content, count=len(lines))


class SkippedEntry(BaseModel):
    raw: str
    reason: str


class EbkGroupResult(BaseModel):
    group: str
    watchlist_id: int
    parsed: int
    added: int
    skipped: list[SkippedEntry] = []


class EbkImportResult(BaseModel):
    groups: list[EbkGroupResult] = []
    total_added: int = 0


def _group_name(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    for ext in (".ebk", ".csv", ".txt"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
    return base.strip() or "Futu 导入"


def _watchlist_id_for(name: str) -> int:
    for wl in list_watchlists():
        if wl.name == name:
            return wl.id
    return create_watchlist(name).id


def import_ebk_files(files: list[dict]) -> EbkImportResult:
    """Import one LU watchlist per file. ``files`` = ``[{"name": ..., "content": ...}]``.

    The filename (sans extension) becomes the group/watchlist name. Equity entries are
    added (deduped via ``add_item``); non-equity entries are reported as skipped.
    """
    result = EbkImportResult()
    for f in files:
        name = _group_name(str(f.get("name", "")))
        text = str(f.get("content", ""))
        parsed = parse_ebk(text)
        wid = _watchlist_id_for(name)
        added = 0
        skipped: list[SkippedEntry] = []
        # Count only symbols not already in the group — re-importing the same .ebk must
        # report added=0, not N (add_item returns the existing item on dedupe).
        wl = get_watchlist(wid)
        present = {it.symbol for it in wl.items} if wl else set()
        for p in parsed:
            if p.kind == "equity" and p.symbol:
                sym = p.symbol.strip().upper()
                if sym in present:
                    continue
                if add_item(wid, sym, tags=name):
                    present.add(sym)
                    added += 1
            else:
                skipped.append(SkippedEntry(raw=p.raw, reason=p.skipped_reason or p.kind))
        result.groups.append(
            EbkGroupResult(
                group=name, watchlist_id=wid, parsed=len(parsed), added=added, skipped=skipped
            )
        )
        result.total_added += added
    return result
