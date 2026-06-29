"use client";

import type { CurvePoint } from "@/lib/api";

export type Series = { name: string; color: string; dashed?: boolean; pts: CurvePoint[] };

/** Overlaid return-% curves (AI agents + benchmark) sharing one axis. */
export default function MultiLineChart({ series, height = 240 }: { series: Series[]; height?: number }) {
  const all = series.flatMap((s) => s.pts);
  const dates = Array.from(new Set(all.map((p) => p.date))).sort();
  if (dates.length < 2) {
    return (
      <p className="text-sm text-ink-faint py-10 text-center">
        {dates.length === 1
          ? "已记录建仓 — 收益曲线将在下一个交易日收盘并同步后展开。"
          : "运行一轮后,这里显示各 AI 的收益曲线对比(% 收益,叠加基准)。"}
      </p>
    );
  }
  const xi = new Map(dates.map((d, i) => [d, i]));
  const W = 760;
  const H = height;
  const padL = 44;
  const padR = 14;
  const padT = 12;
  const padB = 22;
  const vals = all.map((p) => p.value);
  let min = Math.min(...vals, 0);
  let max = Math.max(...vals, 0);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const pad = (max - min) * 0.08;
  min -= pad;
  max += pad;
  const x = (d: string) => padL + (dates.length === 1 ? 0 : (xi.get(d)! / (dates.length - 1)) * (W - padL - padR));
  const y = (v: number) => padT + (1 - (v - min) / (max - min)) * (H - padT - padB);
  const y0 = y(0);

  return (
    <div className="w-full overflow-hidden">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }}>
        {/* y grid: max / 0 / min */}
        {[max - pad, 0, min + pad].map((gv, i) => (
          <g key={i}>
            <line x1={padL} y1={y(gv)} x2={W - padR} y2={y(gv)} stroke="#22272E" strokeWidth={1} strokeDasharray={gv === 0 ? "0" : "2 3"} />
            <text x={padL - 6} y={y(gv) + 3} textAnchor="end" className="fill-ink-faint" fontSize={10}>
              {gv > 0 ? "+" : ""}{gv.toFixed(1)}%
            </text>
          </g>
        ))}
        <line x1={padL} y1={y0} x2={W - padR} y2={y0} stroke="#3A414B" strokeWidth={1} />
        {series.map((s) => {
          const pts = s.pts
            .filter((p) => xi.has(p.date))
            .map((p) => `${x(p.date).toFixed(1)},${y(p.value).toFixed(1)}`)
            .join(" ");
          if (!pts) return null;
          return (
            <polyline
              key={s.name}
              points={pts}
              fill="none"
              stroke={s.color}
              strokeWidth={s.dashed ? 1.5 : 2}
              strokeDasharray={s.dashed ? "5 4" : "0"}
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity={s.dashed ? 0.7 : 1}
            />
          );
        })}
      </svg>
    </div>
  );
}
