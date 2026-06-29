"""AI 竞技场 (#8 模拟交易 + #13 投资人格): persona-driven paper accounts that compete.

Each investor persona (``services.personas``) runs its own virtual cash account with the
same starting capital. On a rebalance *tick*, the persona's LLM looks at the cached facts
for the tracked universe and its current book, then returns a **target allocation**
(weights + 中文 rationale). Python executes the rebalance at cache prices, logs every
fill's reason, and derives a daily equity curve + pro metrics (return / max drawdown /
Sharpe) vs an index benchmark.

Dual-brain: the LLM only *chooses what to hold*; every price, weight, P&L and metric is
computed here. Numbers are never invented by the model.
"""
from __future__ import annotations

import datetime as dt
import json
from bisect import bisect_right

from pydantic import BaseModel
from sqlalchemy import select

from ..compute.perf import PerfMetrics, series_metrics
from ..data import cache
from ..db import session_scope
from ..db.models import PaperAccount, PaperTrade, Snapshot
from ..llm.base import LLMProvider, get_provider, with_chinese
from .paper import _cache_price, _positions
from .personas import Persona, get_persona
from .research import ResearchBundle
from .sync import tracked_symbols

ARENA_START_CASH = 100_000.0
ARENA_ROSTER = ["buffett", "lynch", "livermore", "wood"]  # default 4 competitors
BENCHMARK = ("^GSPC", "标普500")
MAX_UNIVERSE = 40  # cap candidate facts sent to the LLM (keeps the prompt bounded)
_CASH_BUFFER = 0.98  # hard ceiling: never deploy more than 98% of equity
_MIN_TRADE_FRAC = 0.01  # ignore rebalancing churn smaller than 1% of equity (lower turnover)

# Per-style single-position ceiling — a real manager caps concentration. The AI may
# request more, but Python clamps each name to this fraction of equity (rest → cash).
_MAX_POS_BY_STYLE: dict[str, float] = {
    "macro": 0.15,       # Dalio — risk-balanced, most diversified
    "contrarian": 0.20,
    "value": 0.22,
    "growth": 0.25,
    "momentum": 0.28,
    "quant": 0.25,
}
_MAX_POS_DEFAULT = 0.25


def _max_pos(style: str) -> float:
    return _MAX_POS_BY_STYLE.get(style, _MAX_POS_DEFAULT)


def _acct_name(p: Persona) -> str:
    return f"AI·{p.name}"


# ----------------------------------------------------------------------------- accounts
def ensure_arena(roster: list[str] | None = None) -> list[int]:
    """Make sure every persona in the roster has an AI paper account. Returns their ids."""
    roster = roster or ARENA_ROSTER
    ids: list[int] = []
    with session_scope() as s:
        for key in roster:
            p = get_persona(key)
            if p is None:
                continue
            name = _acct_name(p)
            row = s.execute(select(PaperAccount).where(PaperAccount.name == name)).scalar_one_or_none()
            if row is None:
                row = PaperAccount(
                    name=name, cash=ARENA_START_CASH, starting_cash=ARENA_START_CASH,
                    kind="ai", persona=key,
                )
                s.add(row)
                s.flush()
            ids.append(row.id)
    return ids


def _book(account_id: int) -> tuple[float, float, list[PaperTrade], dict]:
    """(cash, starting_cash, trades, derived avg-cost positions) for one account."""
    with session_scope() as s:
        acct = s.get(PaperAccount, account_id)
        trades = list(
            s.execute(select(PaperTrade).where(PaperTrade.account_id == account_id)).scalars()
        )
        cash, starting = acct.cash, acct.starting_cash
    return cash, starting, trades, _positions(trades)


# ----------------------------------------------------------------------------- universe
def _universe_facts() -> list[dict]:
    """Compact cached facts for every tracked symbol — the candidate set the AI can buy."""
    syms = tracked_symbols()
    if not syms:
        return []
    with session_scope() as s:
        snaps = {
            snap.symbol: snap
            for snap in s.execute(select(Snapshot).where(Snapshot.symbol.in_(syms))).scalars()
        }
    facts: list[dict] = []
    for sym in syms:
        snap = snaps.get(sym)
        if not snap or not snap.bundle_json:
            continue
        try:
            b = ResearchBundle.model_validate_json(snap.bundle_json)
        except Exception:  # noqa: BLE001
            continue
        f = b.fundamentals
        facts.append({
            "symbol": b.symbol,
            "name": b.quote.name or f.name,
            "sector": f.sector,
            "price": b.quote.price,
            "change_pct": b.quote.change_pct,
            "pe_ttm": f.pe_ttm,
            "peg": f.peg,
            "pb": f.pb,
            "dividend_yield": f.dividend_yield,
            "market_cap": f.market_cap,
            "trend": b.technical_trend,
            "rsi14": b.technical_latest.get("rsi14"),
        })
    facts.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)
    return facts[:MAX_UNIVERSE]


# ----------------------------------------------------------------------------- decide + trade
class RebalanceResult(BaseModel):
    persona: str
    name: str
    orders: int = 0
    commentary: str = ""
    target_invested_pct: float | None = None  # how much of equity the AI chose to deploy
    error: str | None = None


def _market_regime() -> str:
    """A one-line read on the benchmark's recent trend — fed to every persona for timing."""
    _ds, cs = _bar_index(BENCHMARK[0])
    if len(cs) < 20:
        return "数据不足"
    recent = cs[-20:]
    chg = (recent[-1] / recent[0] - 1) * 100 if recent[0] else 0.0
    ma20 = sum(recent) / len(recent)
    trend = "上行" if chg > 2 else "下行" if chg < -2 else "震荡"
    side = "站上" if cs[-1] >= ma20 else "跌破"
    return f"{trend}(近20日 {chg:+.1f}%,{side}20日均线)"


def _decide(persona: Persona, facts: list[dict], book: dict, cash: float, equity: float,
            *, regime: str, ret_pct: float, max_pos: float, provider: LLMProvider) -> dict:
    holdings = [
        {
            "symbol": sym,
            "qty": round(p["qty"], 4),
            "weight": round((p["qty"] * (_cache_price(sym) or 0)) / equity, 4) if equity else 0,
        }
        for sym, p in book.items()
    ]
    spec = {
        "targets": [{"symbol": "TICKER", "weight": 0.0, "reason": "中文:为什么持有这只、给这个权重"}],
        "commentary": "中文:本轮整体思路与仓位决定(1-2 句)",
    }
    prompt = (
        f"你正在管理一个 {equity:,.0f} USD 的模拟组合,当前现金 {cash:,.0f} USD,"
        f"账户累计收益 {ret_pct:+.1f}%。大盘({BENCHMARK[1]})当前:{regime}。\n"
        f"当前持仓:\n{json.dumps(holdings, ensure_ascii=False)}\n\n"
        f"候选标的(只能从这里选,均为已缓存的事实数据):\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        "请完全按你的投资风格,给出**目标组合**(目标权重 = 占总资产比例,0~1 小数):\n"
        f"1. **像真人一样管理仓位**:机会好就多投、机会差或大盘下行就**主动留现金/降低仓位甚至空仓**——"
        "总仓位不必满,权重之和可以远小于 1(其余即为现金)。\n"
        f"2. **控制集中度**:单只目标权重不要超过 {max_pos:.0%}(系统也会强制截断)。\n"
        "3. **未列出的现有持仓将被清仓**;调仓要克制,别每轮大翻仓。\n"
        "4. 每个标的写一句中文理由。若当下你认为应空仓避险,返回空的 targets 并在 commentary 说明。\n"
        f"只返回 JSON,形如:\n{json.dumps(spec, ensure_ascii=False, indent=2)}"
    )
    system = with_chinese(
        persona.system
        + "\n\nYou are managing a real (paper) portfolio with genuine risk management: size "
        "positions by conviction, hold cash when opportunities are poor or the market is weak, "
        "respect the per-name cap, and keep turnover low. Reason ONLY over the provided facts; "
        "never invent tickers, prices or numbers."
    )
    return provider.generate_json(prompt, system=system)


def _record(account_id: int, sym: str, side: str, qty: float, price: float, note: str | None) -> None:
    with session_scope() as s:
        s.add(PaperTrade(
            account_id=account_id, symbol=sym, side=side,
            quantity=round(qty, 6), price=price, note=(note or None),
        ))


def rebalance_account(account_id: int, facts: list[dict], provider: LLMProvider,
                      *, regime: str | None = None) -> RebalanceResult:
    """Ask the persona for a target allocation, then trade to reach it (sells first).

    Risk management is enforced here in Python (not trusted to the LLM): each name is
    capped to the style's max position, and total deployment is whatever the persona
    chose (it may legitimately hold cash) up to the hard 98% ceiling."""
    with session_scope() as s:
        acct = s.get(PaperAccount, account_id)
        persona = get_persona(acct.persona or "")
        name = acct.name
    if persona is None:
        return RebalanceResult(persona="", name=name, error="unknown persona")
    if not facts:
        return RebalanceResult(persona=persona.key, name=name,
                               error="候选池为空 — 请先到自选添加标的并点『全部更新』")

    cash, starting, _trades, held = _book(account_id)
    prices: dict[str, float | None] = {}

    def price(sym: str) -> float | None:
        if sym not in prices:
            prices[sym] = _cache_price(sym)
        return prices[sym]

    invested = sum((price(sym) or 0) * p["qty"] for sym, p in held.items())
    equity = cash + invested
    if equity <= 0:
        return RebalanceResult(persona=persona.key, name=name, error="账户权益为 0")

    ret_pct = (equity / starting - 1) * 100 if starting else 0.0
    max_pos = _max_pos(persona.style)
    if regime is None:
        regime = _market_regime()

    try:
        out = _decide(persona, facts, held, cash, equity,
                      regime=regime, ret_pct=ret_pct, max_pos=max_pos, provider=provider)
    except Exception as e:  # noqa: BLE001
        return RebalanceResult(persona=persona.key, name=name, error=f"LLM 决策失败: {e}")

    valid = {f["symbol"] for f in facts}
    targets: dict[str, tuple[float, str]] = {}
    for t in (out.get("targets") or []):
        sym = str(t.get("symbol", "")).upper()
        w = t.get("weight")
        if sym in valid and isinstance(w, (int, float)) and w > 0:
            targets[sym] = (min(float(w), max_pos), str(t.get("reason", "") or "")[:200])  # cap concentration
    tot = sum(w for w, _ in targets.values())
    scale = (_CASH_BUFFER / tot) if tot > _CASH_BUFFER else 1.0  # only scale down if over the ceiling
    target_invested = min(tot, _CASH_BUFFER)  # final deployed fraction (rest = cash)

    # Plan deltas vs the *current* book (rebalance-to-target).
    min_notional = max(1.0, equity * _MIN_TRADE_FRAC)
    plan: list[tuple[str, float, str, float]] = []  # (sym, delta_qty, reason, price)
    for sym in set(held) | set(targets):
        p = price(sym)
        if not p or p <= 0:
            continue
        cur = held.get(sym, {}).get("qty", 0.0)
        w, reason = targets.get(sym, (0.0, ""))
        w *= scale
        if w == 0 and not reason:
            reason = "清仓:已不在目标组合中"
        tgt_qty = (w * equity) / p
        delta = tgt_qty - cur
        if abs(delta) * p < min_notional:
            continue
        plan.append((sym, delta, reason, p))

    orders = 0
    # Sells first (free up cash), then buys clipped to available cash.
    for sym, delta, reason, p in sorted(plan, key=lambda x: x[1]):
        if delta < 0:
            qty = min(-delta, held.get(sym, {}).get("qty", 0.0))
            if qty <= 0:
                continue
            _record(account_id, sym, "sell", qty, p, reason)
            cash += p * qty
            orders += 1
    for sym, delta, reason, p in sorted(plan, key=lambda x: -x[1]):
        if delta > 0:
            qty = delta
            if qty * p > cash:
                qty = cash / p
            if qty * p < min_notional:
                continue
            _record(account_id, sym, "buy", qty, p, reason)
            cash -= qty * p
            orders += 1

    with session_scope() as s:
        s.get(PaperAccount, account_id).cash = round(cash, 4)

    return RebalanceResult(
        persona=persona.key, name=name, orders=orders,
        commentary=str(out.get("commentary", "") or "")[:300],
        target_invested_pct=round(target_invested * 100, 1),
    )


def run_arena_tick(roster: list[str] | None = None) -> list[RebalanceResult]:
    """One competition round: every persona rebalances against the latest cached facts."""
    ids = ensure_arena(roster)
    try:  # warm the benchmark's bars so the equity curve has an index line
        from ..data.router import get_router
        get_router().get_ohlcv(BENCHMARK[0], period="1y", interval="1d")
    except Exception:  # noqa: BLE001
        pass
    facts = _universe_facts()
    regime = _market_regime()  # computed once, shared across personas this round
    provider = get_provider()
    return [rebalance_account(aid, facts, provider, regime=regime) for aid in ids]


# ----------------------------------------------------------------------------- equity curve
def _bar_index(symbol: str) -> tuple[list[dt.date], list[float]]:
    rows = cache.read_bars(symbol, "1d")
    return [r.date for r in rows], [r.close for r in rows]


def _close_on_or_before(dates: list[dt.date], closes: list[float], d: dt.date) -> float | None:
    i = bisect_right(dates, d) - 1
    return closes[i] if i >= 0 else None


def equity_curve(account_id: int, master_dates: list[dt.date]) -> list[tuple[dt.date, float]]:
    """Reconstruct the account's daily equity over ``master_dates`` from the trade ledger
    + cached daily closes. Cash changes on trade dates; positions are marked to the close
    on or before each date."""
    _cash, starting, trades, _held = _book(account_id)
    if not trades:
        return []
    trades = sorted(trades, key=lambda t: (t.created_at or dt.datetime.min, t.id))
    tdates = [((t.created_at.date() if t.created_at else dt.date.today()), t) for t in trades]
    first = tdates[0][0]
    bars = {sym: _bar_index(sym) for sym in {t.symbol for t in trades}}

    dates = sorted({d for d in master_dates if d >= first} | {td for td, _ in tdates})
    if not dates:
        return []

    curve: list[tuple[dt.date, float]] = []
    ti = 0
    cash = starting
    pos: dict[str, float] = {}
    for d in dates:
        while ti < len(tdates) and tdates[ti][0] <= d:
            t = tdates[ti][1]
            signed = t.quantity if t.side == "buy" else -t.quantity
            cash += -t.price * t.quantity if t.side == "buy" else t.price * t.quantity
            pos[t.symbol] = pos.get(t.symbol, 0.0) + signed
            ti += 1
        mv = 0.0
        for sym, qty in pos.items():
            if qty <= 1e-9:
                continue
            ds, cs = bars.get(sym, ([], []))
            c = _close_on_or_before(ds, cs, d)
            if c:
                mv += qty * c
        curve.append((d, round(cash + mv, 2)))
    return curve


# ----------------------------------------------------------------------------- overview
class ArenaPosition(BaseModel):
    symbol: str
    name: str | None = None
    sector: str | None = None
    quantity: float
    avg_cost: float
    price: float | None = None
    market_value: float
    weight: float
    pnl: float
    pnl_pct: float | None = None
    last_reason: str | None = None


class CurvePoint(BaseModel):
    date: str
    value: float  # return % from the account's start (so all lines share one axis)


class ArenaAgent(BaseModel):
    persona: str
    name: str
    tagline: str
    style: str
    cash: float
    invested: float
    equity: float
    starting_cash: float
    metrics: PerfMetrics
    positions: list[ArenaPosition]
    trades_count: int
    last_decision_at: dt.datetime | None = None
    rank: int = 0
    curve: list[CurvePoint] = []


class BenchmarkOut(BaseModel):
    symbol: str
    name: str
    return_pct: float | None = None
    curve: list[CurvePoint] = []


class ArenaOut(BaseModel):
    agents: list[ArenaAgent]
    benchmark: BenchmarkOut
    universe_size: int
    updated_at: dt.datetime | None = None


def _name_lookup(symbols: set[str]) -> dict[str, tuple[str | None, str | None]]:
    """symbol -> (name, sector) from cached snapshots."""
    if not symbols:
        return {}
    out: dict[str, tuple[str | None, str | None]] = {}
    with session_scope() as s:
        for snap in s.execute(select(Snapshot).where(Snapshot.symbol.in_(symbols))).scalars():
            if not snap.bundle_json:
                continue
            try:
                b = ResearchBundle.model_validate_json(snap.bundle_json)
                out[snap.symbol] = (b.quote.name or b.fundamentals.name, b.fundamentals.sector)
            except Exception:  # noqa: BLE001
                pass
    return out


def get_arena(roster: list[str] | None = None) -> ArenaOut:
    """Leaderboard + equity curves + benchmark for the AI arena."""
    ids = ensure_arena(roster)

    # Calendar = every traded symbol's daily bars (refreshed by the daily sync, so the
    # curve mark-to-markets forward between ticks) ∪ the benchmark's bars.
    with session_scope() as s:
        traded = set(s.execute(
            select(PaperTrade.symbol).where(PaperTrade.account_id.in_(ids))
        ).scalars())
    bench_dates, bench_closes = _bar_index(BENCHMARK[0])
    cal: set[dt.date] = set(bench_dates)
    for sym in traded:
        cal.update(_bar_index(sym)[0])
    master = sorted(cal)

    agents: list[ArenaAgent] = []
    earliest: dt.date | None = None
    for aid in ids:
        cash, starting, trades, held = _book(aid)
        with session_scope() as s:
            acct = s.get(PaperAccount, aid)
            persona = get_persona(acct.persona or "")
        if persona is None:
            continue

        # latest buy rationale per symbol, and last decision time
        last_reason: dict[str, str] = {}
        last_at: dt.datetime | None = None
        for t in sorted(trades, key=lambda x: (x.created_at or dt.datetime.min, x.id)):
            if t.note and t.side == "buy":
                last_reason[t.symbol] = t.note
            if t.created_at and (last_at is None or t.created_at > last_at):
                last_at = t.created_at

        names = _name_lookup(set(held))
        positions: list[ArenaPosition] = []
        invested = 0.0
        for sym, p in held.items():
            qty = p["qty"]
            avg = p["cost"] / qty if qty else 0.0
            price = _cache_price(sym)
            mv = (price or avg) * qty
            invested += mv
            nm, sec = names.get(sym, (None, None))
            positions.append(ArenaPosition(
                symbol=sym, name=nm, sector=sec, quantity=round(qty, 4), avg_cost=round(avg, 4),
                price=price, market_value=round(mv, 2), weight=0.0,
                pnl=round(mv - p["cost"], 2),
                pnl_pct=((mv - p["cost"]) / p["cost"] * 100 if p["cost"] else None),
                last_reason=last_reason.get(sym),
            ))
        equity = cash + invested
        for pos in positions:
            pos.weight = pos.market_value / equity if equity else 0.0
        positions.sort(key=lambda x: x.market_value, reverse=True)

        raw = equity_curve(aid, master)
        if raw:
            earliest = raw[0][0] if earliest is None else min(earliest, raw[0][0])
        eqs = [e for _, e in raw]
        if len(eqs) >= 2:
            metrics = series_metrics(eqs, starting)
        else:
            metrics = PerfMetrics(total_return_pct=round((equity / starting - 1) * 100, 2) if starting else 0.0)
        curve = [CurvePoint(date=d.isoformat(), value=round((e / starting - 1) * 100, 3)) for d, e in raw]

        agents.append(ArenaAgent(
            persona=persona.key, name=acct.name, tagline=persona.tagline, style=persona.style,
            cash=round(cash, 2), invested=round(invested, 2), equity=round(equity, 2),
            starting_cash=starting, metrics=metrics, positions=positions,
            trades_count=len(trades), last_decision_at=last_at, curve=curve,
        ))

    agents.sort(key=lambda a: (a.metrics.total_return_pct if a.metrics.total_return_pct is not None else -1e9), reverse=True)
    for i, a in enumerate(agents):
        a.rank = i + 1

    # Benchmark: same trading calendar, normalized to % from the arena's earliest activity.
    bench = BenchmarkOut(symbol=BENCHMARK[0], name=BENCHMARK[1])
    if bench_dates and earliest is not None:
        base = _close_on_or_before(bench_dates, bench_closes, earliest)
        if base:
            pts = [(d, c) for d, c in zip(bench_dates, bench_closes) if d >= earliest]
            bench.curve = [CurvePoint(date=d.isoformat(), value=round((c / base - 1) * 100, 3)) for d, c in pts]
            if bench.curve:
                bench.return_pct = bench.curve[-1].value

    last_updated = max((a.last_decision_at for a in agents if a.last_decision_at), default=None)
    return ArenaOut(agents=agents, benchmark=bench, universe_size=len(tracked_symbols()),
                    updated_at=last_updated)


def reset_arena(roster: list[str] | None = None) -> ArenaOut:
    """Wipe all AI accounts' trades and restore starting cash."""
    ids = ensure_arena(roster)
    with session_scope() as s:
        for aid in ids:
            for t in s.execute(select(PaperTrade).where(PaperTrade.account_id == aid)).scalars():
                s.delete(t)
            acct = s.get(PaperAccount, aid)
            acct.cash = acct.starting_cash
    return get_arena(roster)
