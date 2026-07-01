"""Deterministic price-pattern detection — candlestick patterns + a couple of classic chart
formations (double top/bottom). Pure geometry over OHLC bars; every hit is rule-based and
explainable, so it stays first-class compute output the LLM only narrates (never invents).

Bias convention matches the app: bullish → red/up, bearish → green/down (A-share).
"""
from __future__ import annotations

from pydantic import BaseModel

from ..data.base import Bar


class PatternHit(BaseModel):
    date: str
    name: str                 # Chinese display name
    kind: str                 # bullish | bearish | neutral
    category: str             # candle | chart
    detail: str | None = None


def _body(b: Bar) -> float:
    return abs(b.close - b.open)


def _range(b: Bar) -> float:
    return b.high - b.low


def _upper(b: Bar) -> float:
    return b.high - max(b.open, b.close)


def _lower(b: Bar) -> float:
    return min(b.open, b.close) - b.low


def _is_bull(b: Bar) -> bool:
    return b.close > b.open


def _candle(bars: list[Bar], i: int) -> PatternHit | None:
    """Classify a single candlestick (with 1-2 bars of context) at index i."""
    b = bars[i]
    rng = _range(b)
    if rng <= 0:
        return None
    body = _body(b)
    up, lo = _upper(b), _lower(b)
    d = b.date.isoformat()

    # Doji: negligible body.
    if body <= 0.1 * rng:
        return PatternHit(date=d, name="十字星", kind="neutral", category="candle",
                          detail="开收几乎相等,多空胶着")

    # Hammer / hanging man: small body near top, long lower shadow.
    if lo >= 2 * body and up <= body and body <= 0.4 * rng:
        return PatternHit(date=d, name="锤子线", kind="bullish", category="candle",
                          detail="长下影,下方买盘承接")
    # Inverted hammer / shooting star: long upper shadow.
    if up >= 2 * body and lo <= body and body <= 0.4 * rng:
        kind = "bearish" if i > 0 and _is_bull(bars[i - 1]) else "bullish"
        return PatternHit(date=d, name="流星线" if kind == "bearish" else "倒锤线",
                          kind=kind, category="candle", detail="长上影,上方抛压")

    # Engulfing (needs a prior bar).
    if i > 0:
        p = bars[i - 1]
        if _is_bull(b) and not _is_bull(p) and b.close >= p.open and b.open <= p.close and _body(b) > _body(p):
            return PatternHit(date=d, name="看涨吞没", kind="bullish", category="candle",
                              detail="阳线完全吞没前根阴线")
        if not _is_bull(b) and _is_bull(p) and b.open >= p.close and b.close <= p.open and _body(b) > _body(p):
            return PatternHit(date=d, name="看跌吞没", kind="bearish", category="candle",
                              detail="阴线完全吞没前根阳线")

    # Star patterns (3 bars): small middle body gapping from two larger opposite bodies.
    if i >= 2:
        a, m = bars[i - 2], bars[i - 1]
        if _is_bull(a) is False and _body(m) <= 0.5 * _body(a) and _is_bull(b) and b.close > (a.open + a.close) / 2:
            return PatternHit(date=d, name="启明星", kind="bullish", category="candle",
                              detail="下跌后小实体反转,阳线收复过半")
        if _is_bull(a) and _body(m) <= 0.5 * _body(a) and not _is_bull(b) and b.close < (a.open + a.close) / 2:
            return PatternHit(date=d, name="黄昏星", kind="bearish", category="candle",
                              detail="上涨后小实体反转,阴线跌破过半")
    return None


def _three_soldiers(bars: list[Bar]) -> PatternHit | None:
    if len(bars) < 3:
        return None
    last3 = bars[-3:]
    if all(_is_bull(b) and _body(b) > 0.5 * _range(b) for b in last3) and \
       last3[0].close < last3[1].close < last3[2].close:
        return PatternHit(date=last3[-1].date.isoformat(), name="红三兵", kind="bullish",
                          category="candle", detail="三连阳节节走高")
    if all(not _is_bull(b) and _body(b) > 0.5 * _range(b) for b in last3) and \
       last3[0].close > last3[1].close > last3[2].close:
        return PatternHit(date=last3[-1].date.isoformat(), name="三只乌鸦", kind="bearish",
                          category="candle", detail="三连阴节节走低")
    return None


def _swings(bars: list[Bar], w: int = 3) -> tuple[list[int], list[int]]:
    """Indices of local swing highs / lows (strict local extrema over a ±w window)."""
    highs, lows = [], []
    for i in range(w, len(bars) - w):
        window = bars[i - w:i + w + 1]
        if bars[i].high == max(x.high for x in window) and \
           bars[i].high > max(x.high for x in window[:w] + window[w + 1:]):
            highs.append(i)
        if bars[i].low == min(x.low for x in window) and \
           bars[i].low < min(x.low for x in window[:w] + window[w + 1:]):
            lows.append(i)
    return highs, lows


def _double_patterns(bars: list[Bar]) -> list[PatternHit]:
    """Double top / double bottom: two comparable swing extrema (~within 3%) recently."""
    out: list[PatternHit] = []
    if len(bars) < 20:
        return out
    highs, lows = _swings(bars)
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if b >= len(bars) - 15 and abs(bars[a].high - bars[b].high) <= 0.03 * bars[a].high:
            out.append(PatternHit(date=bars[b].date.isoformat(), name="双顶(M头)", kind="bearish",
                                  category="chart", detail="两次冲高受阻于相近价位"))
    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if b >= len(bars) - 15 and abs(bars[a].low - bars[b].low) <= 0.03 * max(bars[a].low, 1e-9):
            out.append(PatternHit(date=bars[b].date.isoformat(), name="双底(W底)", kind="bullish",
                                  category="chart", detail="两次探底获相近价位支撑"))
    return out


def detect_patterns(bars: list[Bar], *, recent: int = 10) -> list[PatternHit]:
    """Detect candlestick patterns over the last ``recent`` bars + chart formations over the
    whole series. Returns newest-first."""
    hits: list[PatternHit] = []
    n = len(bars)
    if n < 2:
        return hits
    start = max(1, n - recent)
    for i in range(start, n):
        hit = _candle(bars, i)
        if hit:
            hits.append(hit)
    soldiers = _three_soldiers(bars)
    if soldiers:
        hits.append(soldiers)
    hits.extend(_double_patterns(bars))
    # De-dup by (date, name); newest-first.
    seen: set[tuple[str, str]] = set()
    uniq: list[PatternHit] = []
    for h in sorted(hits, key=lambda x: x.date, reverse=True):
        k = (h.date, h.name)
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    return uniq
