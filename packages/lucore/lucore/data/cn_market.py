"""A-share market-breadth feeds via akshare (东方财富): limit-up pool, dragon-tiger
list, and 沪深港通 (HSGT) flow summary.

These are market-wide (not per-symbol), so they live outside MarketDataAdapter.
akshare scrapes Chinese sites and can rate-limit / change columns, so every fetch is
defensive: a missing field degrades to None and a failure raises (the caller catches).

NOTE: real-time **northbound** (北向) net flow has been suspended by the exchanges since
2024-08, so HSGT 北向 amounts now read 0 — we still surface the breadth + 南向 (港股通).
"""
from __future__ import annotations

from pydantic import BaseModel


# ----------------------------- models -----------------------------
class LimitUpStock(BaseModel):
    code: str
    name: str
    pct: float | None = None            # 涨跌幅 %
    price: float | None = None          # 最新价
    amount: float | None = None         # 成交额 (元)
    float_cap: float | None = None      # 流通市值
    turnover: float | None = None       # 换手率 %
    seal_fund: float | None = None      # 封板资金 (元)
    first_seal: str | None = None       # 首次封板时间 HH:MM
    last_seal: str | None = None        # 最后封板时间 HH:MM
    broken_times: int | None = None     # 炸板次数
    boards: int | None = None           # 连板数
    streak: str | None = None           # 涨停统计 e.g. "9/6"
    industry: str | None = None         # 所属行业


class LimitUpPool(BaseModel):
    date: str
    count: int = 0
    stocks: list[LimitUpStock] = []


class DragonTigerRow(BaseModel):
    code: str
    name: str
    date: str | None = None             # 上榜日
    interpret: str | None = None        # 解读
    close: float | None = None          # 收盘价
    pct: float | None = None            # 涨跌幅 %
    net_buy: float | None = None        # 龙虎榜净买额 (元)
    buy: float | None = None            # 龙虎榜买入额
    sell: float | None = None           # 龙虎榜卖出额
    net_pct: float | None = None        # 净买额占总成交比 %
    turnover: float | None = None       # 换手率 %
    reason: str | None = None           # 上榜原因


class DragonTiger(BaseModel):
    date: str
    count: int = 0
    rows: list[DragonTigerRow] = []


class HsgtFlowRow(BaseModel):
    date: str | None = None
    market: str | None = None           # 板块: 沪股通 / 深股通 / 港股通(沪) ...
    direction: str | None = None        # 资金方向: 北向 / 南向
    net: float | None = None            # 成交净买额 (亿元)
    inflow: float | None = None         # 资金净流入 (亿元)
    up: int | None = None               # 上涨数
    flat: int | None = None             # 持平数
    down: int | None = None             # 下跌数
    index_name: str | None = None       # 相关指数
    index_pct: float | None = None      # 指数涨跌幅 %


class HsgtSummary(BaseModel):
    date: str | None = None
    northbound_suspended: bool = True   # 北向实时净额自 2024-08 起停发
    rows: list[HsgtFlowRow] = []


# ----------------------------- helpers -----------------------------
def _ak():
    import akshare as ak  # lazy: heavy import, optional install
    return ak


def _f(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _i(v) -> int | None:
    f = _f(v)
    return int(f) if f is not None else None


def _s(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _hhmm(v) -> str | None:
    """'092500' -> '09:25'."""
    s = _s(v)
    if not s:
        return None
    s = s.zfill(6)
    return f"{s[0:2]}:{s[2:4]}" if len(s) >= 4 else s


# ----------------------------- fetchers -----------------------------
def fetch_limit_up_pool(date: str) -> LimitUpPool:
    """date as 'YYYYMMDD'. Today's 涨停股池 from 东方财富."""
    df = _ak().stock_zt_pool_em(date=date)
    stocks: list[LimitUpStock] = []
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            stocks.append(LimitUpStock(
                code=_s(r.get("代码")) or "",
                name=_s(r.get("名称")) or "",
                pct=_f(r.get("涨跌幅")), price=_f(r.get("最新价")),
                amount=_f(r.get("成交额")), float_cap=_f(r.get("流通市值")),
                turnover=_f(r.get("换手率")), seal_fund=_f(r.get("封板资金")),
                first_seal=_hhmm(r.get("首次封板时间")), last_seal=_hhmm(r.get("最后封板时间")),
                broken_times=_i(r.get("炸板次数")), boards=_i(r.get("连板数")),
                streak=_s(r.get("涨停统计")), industry=_s(r.get("所属行业")),
            ))
    return LimitUpPool(date=date, count=len(stocks), stocks=stocks)


def fetch_dragon_tiger(date: str) -> DragonTiger:
    """date as 'YYYYMMDD'. 龙虎榜 detail for that single day."""
    df = _ak().stock_lhb_detail_em(start_date=date, end_date=date)
    rows: list[DragonTigerRow] = []
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            d = r.get("上榜日")
            rows.append(DragonTigerRow(
                code=_s(r.get("代码")) or "",
                name=_s(r.get("名称")) or "",
                date=_s(d), interpret=_s(r.get("解读")),
                close=_f(r.get("收盘价")), pct=_f(r.get("涨跌幅")),
                net_buy=_f(r.get("龙虎榜净买额")), buy=_f(r.get("龙虎榜买入额")),
                sell=_f(r.get("龙虎榜卖出额")), net_pct=_f(r.get("净买额占总成交比")),
                turnover=_f(r.get("换手率")), reason=_s(r.get("上榜原因")),
            ))
    return DragonTiger(date=date, count=len(rows), rows=rows)


def fetch_hsgt_summary() -> HsgtSummary:
    """沪深港通资金流向汇总(含北向/南向)。北向实时净额已停发,值多为 0。"""
    df = _ak().stock_hsgt_fund_flow_summary_em()
    rows: list[HsgtFlowRow] = []
    date = None
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            date = _s(r.get("交易日")) or date
            rows.append(HsgtFlowRow(
                date=_s(r.get("交易日")), market=_s(r.get("板块")),
                direction=_s(r.get("资金方向")), net=_f(r.get("成交净买额")),
                inflow=_f(r.get("资金净流入")), up=_i(r.get("上涨数")),
                flat=_i(r.get("持平数")), down=_i(r.get("下跌数")),
                index_name=_s(r.get("相关指数")), index_pct=_f(r.get("指数涨跌幅")),
            ))
    return HsgtSummary(date=date, rows=rows)
