"""Brinson-Hood-Beebower performance attribution: decompose a portfolio's active return
(vs a benchmark) into allocation / selection / interaction effects by segment (sector).

Pure math (weights & returns as fractions in; percentages out). Identity holds:
Σ(alloc+select+interact) == Σ wp·rp − Σ wb·rb == portfolio_return − benchmark_return.
"""
from __future__ import annotations

from pydantic import BaseModel


class SegmentEffect(BaseModel):
    segment: str
    port_weight: float          # % (0..100)
    bench_weight: float
    port_return_pct: float
    bench_return_pct: float
    allocation: float           # contribution to active return, %
    selection: float
    interaction: float


class Attribution(BaseModel):
    benchmark: str = "等权基准"
    segments: list[SegmentEffect] = []
    port_return_pct: float = 0.0
    bench_return_pct: float = 0.0
    allocation_pct: float = 0.0
    selection_pct: float = 0.0
    interaction_pct: float = 0.0
    total_active_pct: float = 0.0


def brinson(segments: list[dict], benchmark: str = "等权基准") -> Attribution:
    """`segments`: list of {segment, wp, rp, wb, rb} with weights & returns as FRACTIONS
    (wp/wb sum to ~1 across segments; rp/rb are period returns e.g. 0.12 == +12%)."""
    effs: list[SegmentEffect] = []
    alloc_t = select_t = inter_t = port_t = bench_t = 0.0
    for s in segments:
        wp = float(s.get("wp", 0.0))
        wb = float(s.get("wb", 0.0))
        rp = float(s.get("rp", 0.0))
        rb = float(s.get("rb", 0.0))
        alloc = (wp - wb) * rb
        select = wb * (rp - rb)
        inter = (wp - wb) * (rp - rb)
        alloc_t += alloc
        select_t += select
        inter_t += inter
        port_t += wp * rp
        bench_t += wb * rb
        effs.append(SegmentEffect(
            segment=str(s.get("segment", "—")),
            port_weight=round(wp * 100, 2), bench_weight=round(wb * 100, 2),
            port_return_pct=round(rp * 100, 2), bench_return_pct=round(rb * 100, 2),
            allocation=round(alloc * 100, 2), selection=round(select * 100, 2),
            interaction=round(inter * 100, 2),
        ))
    return Attribution(
        benchmark=benchmark, segments=effs,
        port_return_pct=round(port_t * 100, 2), bench_return_pct=round(bench_t * 100, 2),
        allocation_pct=round(alloc_t * 100, 2), selection_pct=round(select_t * 100, 2),
        interaction_pct=round(inter_t * 100, 2), total_active_pct=round((port_t - bench_t) * 100, 2),
    )
