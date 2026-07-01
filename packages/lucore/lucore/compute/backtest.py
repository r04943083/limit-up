"""Deterministic strategy backtester (#9).

Pure functions over OHLCV bars — no DB, no network, no LLM. Supports a small rule DSL
(RSI thresholds, SMA cross, N-day breakout). Long-only, all-in/all-out, fills at the
signal bar's close. Returns an equity curve, the trade list and summary stats so the
web app can chart it and the LLM can narrate it.
"""
from __future__ import annotations

import math

from pydantic import BaseModel, Field

from ..data.base import Bar

STRATEGIES = ["rsi", "ma_cross", "breakout"]


class StrategySpec(BaseModel):
    kind: str = "ma_cross"  # rsi | ma_cross | breakout
    # rsi
    rsi_period: int = Field(14, ge=1)
    rsi_buy: float = 30.0
    rsi_sell: float = 70.0
    # ma_cross
    fast: int = Field(20, ge=1)
    slow: int = Field(50, ge=1)
    # breakout — windows must be ≥1 or the rolling max/min slices are empty (ValueError)
    lookback: int = Field(20, ge=1)
    exit_lookback: int = Field(10, ge=1)
    starting_cash: float = Field(10_000.0, gt=0)


class BacktestPoint(BaseModel):
    date: str
    equity: float
    buy_hold: float


class BacktestTrade(BaseModel):
    entry_date: str
    exit_date: str | None
    entry_price: float
    exit_price: float | None
    return_pct: float | None
    bars_held: int


class BacktestStats(BaseModel):
    total_return_pct: float
    buy_hold_return_pct: float
    cagr_pct: float | None
    max_drawdown_pct: float
    win_rate: float | None
    trades: int
    sharpe: float | None
    exposure_pct: float  # % of bars in the market


class BacktestResult(BaseModel):
    symbol: str
    kind: str
    bars: int
    spec: StrategySpec
    stats: BacktestStats
    curve: list[BacktestPoint] = []
    trade_log: list[BacktestTrade] = Field(default_factory=list)


def _sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        out.append(s / window if i >= window - 1 else None)
    return out


def _rsi(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        ch = values[i] - values[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, len(values)):
        ch = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(ch, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-ch, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def _signals(closes: list[float], highs: list[float], lows: list[float], spec: StrategySpec) -> list[int]:
    """Per-bar desired state: 1 = want to be long, 0 = want to be flat. -1 = no signal (hold)."""
    n = len(closes)
    want = [-1] * n
    if spec.kind == "rsi":
        rsi = _rsi(closes, spec.rsi_period)
        for i in range(n):
            if rsi[i] is None:
                continue
            if rsi[i] <= spec.rsi_buy:
                want[i] = 1
            elif rsi[i] >= spec.rsi_sell:
                want[i] = 0
    elif spec.kind == "ma_cross":
        fast = _sma(closes, spec.fast)
        slow = _sma(closes, spec.slow)
        for i in range(n):
            if fast[i] is None or slow[i] is None:
                continue
            want[i] = 1 if fast[i] > slow[i] else 0
    elif spec.kind == "breakout":
        for i in range(n):
            if i < spec.lookback:
                continue
            hi = max(highs[i - spec.lookback:i])
            lo = min(lows[max(0, i - spec.exit_lookback):i])
            if closes[i] >= hi:
                want[i] = 1
            elif closes[i] <= lo:
                want[i] = 0
    return want


def backtest(symbol: str, bars: list[Bar], spec: StrategySpec) -> BacktestResult:
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    dates = [b.date.isoformat() for b in bars]
    n = len(bars)
    want = _signals(closes, highs, lows, spec)

    cash = spec.starting_cash
    shares = 0.0
    in_market_bars = 0
    curve: list[BacktestPoint] = []
    trades: list[BacktestTrade] = []
    open_entry: tuple[int, float] | None = None
    bh0 = closes[0] if closes else 1.0
    peak = spec.starting_cash
    max_dd = 0.0
    daily_rets: list[float] = []
    prev_equity = spec.starting_cash

    for i in range(n):
        target = want[i]
        price = closes[i]
        if target == 1 and shares == 0:  # enter long
            shares = cash / price
            cash = 0.0
            open_entry = (i, price)
        elif target == 0 and shares > 0:  # exit
            cash = shares * price
            shares = 0.0
            if open_entry:
                ei, ep = open_entry
                trades.append(BacktestTrade(
                    entry_date=dates[ei], exit_date=dates[i], entry_price=round(ep, 4),
                    exit_price=round(price, 4), return_pct=(price / ep - 1), bars_held=i - ei,
                ))
                open_entry = None
        equity = cash + shares * price
        if shares > 0:
            in_market_bars += 1
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
        if prev_equity > 0:
            daily_rets.append(equity / prev_equity - 1)
        prev_equity = equity
        curve.append(BacktestPoint(
            date=dates[i], equity=round(equity, 2),
            buy_hold=round(spec.starting_cash * price / bh0, 2),
        ))

    final_equity = cash + shares * (closes[-1] if closes else 0.0)
    if open_entry:  # mark open trade
        ei, ep = open_entry
        trades.append(BacktestTrade(
            entry_date=dates[ei], exit_date=None, entry_price=round(ep, 4), exit_price=None,
            return_pct=(closes[-1] / ep - 1) if closes else None, bars_held=n - 1 - ei,
        ))

    closed = [t for t in trades if t.exit_date is not None and t.return_pct is not None]
    wins = sum(1 for t in closed if t.return_pct > 0)
    total_ret = final_equity / spec.starting_cash - 1 if spec.starting_cash else 0.0
    bh_ret = (closes[-1] / bh0 - 1) if closes else 0.0
    years = n / 252.0 if n else 0.0
    cagr = ((final_equity / spec.starting_cash) ** (1 / years) - 1) if years > 0.1 and final_equity > 0 else None
    mean_r = sum(daily_rets) / len(daily_rets) if daily_rets else 0.0
    var = sum((r - mean_r) ** 2 for r in daily_rets) / len(daily_rets) if daily_rets else 0.0
    std = math.sqrt(var)
    sharpe = (mean_r / std * math.sqrt(252)) if std > 1e-12 else None

    stats = BacktestStats(
        total_return_pct=total_ret, buy_hold_return_pct=bh_ret, cagr_pct=cagr,
        max_drawdown_pct=max_dd, win_rate=(wins / len(closed) if closed else None),
        trades=len(closed), sharpe=sharpe, exposure_pct=(in_market_bars / n if n else 0.0),
    )
    return BacktestResult(
        symbol=symbol.upper(), kind=spec.kind, bars=n, spec=spec, stats=stats,
        curve=curve, trade_log=trades,
    )
