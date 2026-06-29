"use client";

import { useEffect, useMemo, useState } from "react";
import Panel from "@/components/Panel";
import { getValuation, type ValuationBand, type ValuationOut } from "@/lib/api";
import { num, signedPct } from "@/lib/format";

/**
 * Futu-style 分析 panel: 历史估值带 (PE/PB/PS) — each metric's history, its 平均水平 (mean
 * line) and 历史分位 (where today sits), plus analyst consensus. All numbers are computed
 * deterministically server-side (cached closes ÷ reported quarterly per-share figures);
 * this component only draws them. Valuation color: 高位=红 (贵), 低位=绿 (便宜).
 */
const METRICS = [
  { key: "pe", label: "市盈率 PE" },
  { key: "pb", label: "市净率 PB" },
  { key: "ps", label: "市销率 PS" },
] as const;
type MetricKey = (typeof METRICS)[number]["key"];

function bandColor(pct: number | null | undefined): string {
  if (pct == null) return "#E0A33E";
  if (pct >= 66) return "#F6465D"; // 高位 / 贵
  if (pct <= 33) return "#2EBD85"; // 低位 / 便宜
  return "#E0A33E";
}

function percentileLabel(pct: number | null | undefined): string {
  if (pct == null) return "—";
  if (pct >= 80) return "历史高位(偏贵)";
  if (pct >= 60) return "中高位";
  if (pct >= 40) return "中位";
  if (pct >= 20) return "中低位";
  return "历史低位(偏便宜)";
}

function BandChart({ band }: { band: ValuationBand }) {
  const W = 600;
  const H = 150;
  const padT = 12;
  const padB = 16;
  const geom = useMemo(() => {
    const pts = band.points;
    if (pts.length < 2) return null;
    const vals = pts.map((p) => p.value);
    const lo = Math.min(...vals, band.current ?? Infinity);
    const hi = Math.max(...vals, band.current ?? -Infinity);
    const span = hi - lo || 1;
    const innerH = H - padT - padB;
    const x = (i: number) => (i / (pts.length - 1)) * W;
    const y = (v: number) => padT + (1 - (v - lo) / span) * innerH;
    const line = pts.map((p, i) => `${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
    const area = `0,${(padT + innerH).toFixed(1)} ${line} ${W},${(padT + innerH).toFixed(1)}`;
    return {
      line,
      area,
      meanY: band.mean != null ? y(band.mean) : null,
      curY: band.current != null ? y(band.current) : null,
      baseY: padT + innerH,
    };
  }, [band]);

  if (!geom) {
    return (
      <div className="h-[150px] grid place-items-center text-ink-faint text-xs text-center px-4">
        该指标历史数据不足(需要至少 4 个季度的财报)。<br />同步财报后将自动展开。
      </div>
    );
  }
  const color = bandColor(band.percentile);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" className="overflow-visible">
      <defs>
        <linearGradient id={`vg-${band.metric}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={geom.area} fill={`url(#vg-${band.metric})`} />
      <polyline points={geom.line} fill="none" stroke={color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      {geom.meanY != null && (
        <line x1="0" y1={geom.meanY} x2={W} y2={geom.meanY} stroke="#8B98A5" strokeWidth={1}
          strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />
      )}
      {geom.curY != null && (
        <>
          <line x1="0" y1={geom.curY} x2={W} y2={geom.curY} stroke={color} strokeWidth={1}
            strokeDasharray="2 3" opacity={0.7} vectorEffect="non-scaling-stroke" />
          <circle cx={W} cy={geom.curY} r={3.5} fill={color} />
        </>
      )}
    </svg>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[11px] text-ink-faint mb-0.5">{label}</div>
      <div className="text-sm font-semibold tnum" style={tone ? { color: tone } : undefined}>{value}</div>
    </div>
  );
}

function recLabel(mean: number | null | undefined): { text: string; tone: string } {
  if (mean == null) return { text: "—", tone: "#8B98A5" };
  if (mean <= 1.5) return { text: "强力买入", tone: "#F6465D" };
  if (mean <= 2.5) return { text: "买入", tone: "#F6465D" };
  if (mean <= 3.5) return { text: "持有", tone: "#E0A33E" };
  if (mean <= 4.5) return { text: "卖出", tone: "#2EBD85" };
  return { text: "强力卖出", tone: "#2EBD85" };
}

export default function ValuationPanel({ symbol }: { symbol: string }) {
  const [val, setVal] = useState<ValuationOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [metric, setMetric] = useState<MetricKey>("pe");

  useEffect(() => {
    setLoading(true);
    setVal(null);
    getValuation(symbol).then(setVal).catch(() => setVal(null)).finally(() => setLoading(false));
  }, [symbol]);

  if (loading) return <p className="text-sm text-ink-faint py-6 text-center">加载估值数据…</p>;
  if (!val) return <p className="text-sm text-ink-faint py-6 text-center">暂无估值数据。</p>;

  const band = val[metric];
  const color = bandColor(band.percentile);
  const a = val.analyst;
  const rec = recLabel(a.recommendation_mean);
  const ccy = val.currency ?? "";

  return (
    <div className="space-y-5">
      <Panel title="历史估值带" hint={band.points.length ? `${band.points.length} 个交易日` : undefined}>
        <div className="flex items-center gap-1 mb-4">
          {METRICS.map((m) => (
            <button key={m.key} onClick={() => setMetric(m.key)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                m.key === metric ? "bg-panel-2 text-ink border border-line" : "text-ink-dim hover:text-ink"
              }`}>
              {m.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-4">
          <Stat label="当前" value={num(band.current)} tone={color} />
          <Stat label="历史平均" value={num(band.mean)} />
          <Stat label="中位数" value={num(band.median)} />
          <Stat label="区间" value={`${num(band.low)} ~ ${num(band.high)}`} />
          <Stat label="历史分位" value={band.percentile != null ? `${band.percentile}%` : "—"} tone={color} />
        </div>

        <BandChart band={band} />

        <div className="flex items-center gap-2 mt-3 text-[11px] text-ink-faint">
          <span className="inline-block w-3 h-0.5" style={{ background: color }} /> {METRICS.find((m) => m.key === metric)?.label}
          <span className="inline-block w-3 border-t border-dashed border-ink-faint ml-2" /> 历史平均
          <span className="ml-auto" style={{ color }}>{percentileLabel(band.percentile)}</span>
        </div>
        <p className="text-[11px] text-ink-faint mt-2 leading-relaxed">
          按缓存日线收盘 ÷ 最近四个季度滚动每股(EPS / 营收每股 / 每股净资产)还原;窗口取决于已同步的季度财报。低分位=相对历史更便宜。
        </p>
      </Panel>

      <Panel title="分析师评级" hint={a.num_analysts != null ? `${a.num_analysts} 位分析师` : undefined}>
        {a.recommendation_mean == null && a.target_mean == null ? (
          <p className="text-sm text-ink-faint py-2">暂无分析师评级数据(数据源未提供)。</p>
        ) : (
          <>
            <div className="flex items-center gap-4 mb-4">
              <div className="text-2xl font-bold" style={{ color: rec.tone }}>{rec.text}</div>
              {a.recommendation_mean != null && (
                <div className="text-xs text-ink-faint">综合评分 <span className="tnum text-ink-dim">{num(a.recommendation_mean)}</span> / 5
                  <span className="text-ink-faint"> (1=强力买入)</span></div>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Stat label="目标均价" value={a.target_mean != null ? `${num(a.target_mean)} ${ccy}` : "—"} />
              <Stat label="最高目标" value={a.target_high != null ? num(a.target_high) : "—"} tone="#F6465D" />
              <Stat label="最低目标" value={a.target_low != null ? num(a.target_low) : "—"} tone="#2EBD85" />
              <Stat label="上行空间" value={signedPct(a.upside_pct)}
                tone={a.upside_pct != null ? (a.upside_pct >= 0 ? "#F6465D" : "#2EBD85") : undefined} />
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
