"""Index constituents — the universe the screener filters over.

A-share members come from akshare (kept current). US (S&P 500 / Nasdaq-100) and HK
(Hang Seng) members are parsed from Wikipedia with a browser User-Agent. Everything is
returned as a list of ``(canonical_symbol, name)`` pairs:

* US      → bare ticker, ``.`` → ``-`` (``BRK.B`` → ``BRK-B``, matching yfinance)
* HK      → ``NNNN.HK`` (zero-padded 4-digit)
* A-share → ``NNNNNN.SS`` (Shanghai) / ``NNNNNN.SZ`` (Shenzhen)

Network failures degrade *per index* (an empty list), so one flaky source never sinks the
others. The ``_fetch_*`` helpers are module-level so tests can monkeypatch them without
touching the network.
"""
from __future__ import annotations

import io
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class IndexDef:
    key: str
    label: str
    market: str  # "CN" | "US" | "HK"


# The indices the user opted into seeding. Order = display order.
INDICES: list[IndexDef] = [
    IndexDef("csi300", "沪深300", "CN"),
    IndexDef("csi500", "中证500", "CN"),
    IndexDef("sse50", "上证50", "CN"),
    IndexDef("star50", "科创50", "CN"),
    IndexDef("chinext", "创业板指", "CN"),
    IndexDef("sp500", "标普500", "US"),
    IndexDef("nasdaq100", "纳斯达克100", "US"),
    IndexDef("hsi", "恒生指数", "HK"),
    IndexDef("hstech", "恒生科技", "HK"),
]
INDEX_BY_KEY: dict[str, IndexDef] = {i.key: i for i in INDICES}

Constituent = tuple[str, str | None]  # (canonical symbol, name or None)

# CSI / SSE / STAR indices exposed by ak.index_stock_cons_csindex.
_CSINDEX_CODE = {"csi300": "000300", "csi500": "000905", "sse50": "000016", "star50": "000688"}

_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NDX_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
_HSI_URL = "https://en.wikipedia.org/wiki/Hang_Seng_Index"

# Hang Seng TECH has no clean machine-readable source, so we keep a curated member list.
# Membership rotates a little over time; for a screening universe an extra valid HK tech
# ticker is harmless (the seed de-dups against HSI). Names are filled in by the snapshot
# fetch, so only the ticker needs to be right.
_HSTECH = [
    "0700.HK", "9988.HK", "3690.HK", "1810.HK", "9618.HK", "1024.HK", "9999.HK",
    "9888.HK", "1211.HK", "2015.HK", "9868.HK", "9866.HK", "0981.HK", "1347.HK",
    "0992.HK", "0285.HK", "2382.HK", "6618.HK", "0241.HK", "1833.HK", "0268.HK",
    "3888.HK", "0780.HK", "2018.HK", "9626.HK", "9961.HK", "9698.HK", "6060.HK",
    "0772.HK", "2400.HK",
]


def _clean(v) -> str | None:  # noqa: ANN001
    s = str(v).strip() if v is not None else ""
    return s or None


def _cn_symbol(code, exchange: str | None = None) -> str | None:  # noqa: ANN001
    """A-share 6-digit code → canonical ``.SS`` / ``.SZ`` symbol."""
    code = str(code).strip().split(".")[0].zfill(6)
    if not code.isdigit():
        return None
    if exchange:
        if "深圳" in exchange or "Shenzhen" in exchange:
            return f"{code}.SZ"
        if "上海" in exchange or "Shanghai" in exchange:
            return f"{code}.SS"
    if code[0] in ("6", "9") or code.startswith("68"):
        return f"{code}.SS"
    if code[0] in ("0", "3", "2"):
        return f"{code}.SZ"
    return None


def _grab(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed wiki hosts
        return r.read().decode("utf-8", "ignore")


def _fetch_cn(key: str) -> list[Constituent]:
    import akshare as ak

    out: list[Constituent] = []
    if key in _CSINDEX_CODE:
        df = ak.index_stock_cons_csindex(symbol=_CSINDEX_CODE[key])
        for r in df.to_dict("records"):
            sym = _cn_symbol(r.get("成分券代码"), r.get("交易所"))
            if sym:
                out.append((sym, _clean(r.get("成分券名称"))))
    elif key == "chinext":
        df = ak.index_stock_cons(symbol="399006")
        for r in df.to_dict("records"):
            sym = _cn_symbol(r.get("品种代码"))
            if sym:
                out.append((sym, _clean(r.get("品种名称"))))
    return out


def _fetch_us(key: str) -> list[Constituent]:
    import pandas as pd

    if key == "sp500":
        df = pd.read_html(io.StringIO(_grab(_SP500_URL)))[0]
        tcol, ncol = "Symbol", "Security"
    else:
        tabs = pd.read_html(io.StringIO(_grab(_NDX_URL)))
        cand = [t for t in tabs if "Ticker" in t.columns]
        if not cand:
            return []
        df, tcol, ncol = cand[-1], "Ticker", "Company"
    out: list[Constituent] = []
    for r in df.to_dict("records"):
        t = str(r.get(tcol, "")).strip().upper().replace(".", "-")
        if t and t.replace("-", "").isalnum() and t.isascii():
            out.append((t, _clean(r.get(ncol))))
    return out


def _fetch_hk(key: str) -> list[Constituent]:
    if key == "hstech":
        return [(s, None) for s in _HSTECH]
    import pandas as pd

    tabs = pd.read_html(io.StringIO(_grab(_HSI_URL)))
    cand = [t for t in tabs if "Ticker" in t.columns]
    if not cand:
        return []
    out: list[Constituent] = []
    for r in cand[0].to_dict("records"):
        digits = "".join(ch for ch in str(r.get("Ticker", "")) if ch.isdigit())
        if digits:
            out.append((f"{int(digits):04d}.HK", _clean(r.get("Name"))))
    return out


def constituents(key: str) -> list[Constituent]:
    """Members of one index as ``(symbol, name)`` pairs. ``[]`` on unknown key or fetch
    failure (so a flaky source degrades gracefully instead of raising)."""
    idef = INDEX_BY_KEY.get(key)
    if not idef:
        return []
    try:
        if idef.market == "CN":
            return _fetch_cn(key)
        if idef.market == "US":
            return _fetch_us(key)
        return _fetch_hk(key)
    except Exception:  # noqa: BLE001 - one bad source shouldn't break a multi-index seed
        return []
