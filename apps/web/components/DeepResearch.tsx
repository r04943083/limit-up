"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Panel from "@/components/Panel";
import {
  getFinancials, getDcf,
  type Financials, type Statement, type DcfView,
} from "@/lib/api";
import { compact, num, signedPct } from "@/lib/format";

type StmtKey = "income" | "balance" | "cashflow";
const STMT_TABS: { key: StmtKey; label: string }[] = [
  { key: "income", label: "利润表" },
  { key: "balance", label: "资产负债表" },
  { key: "cashflow", label: "现金流量表" },
];

// EPS / per-share rows are small numbers — show raw; everything else is currency, show compact.
const isPerShare = (label: string) => /EPS|每股/i.test(label);

function Spark({ values }: { values: (number | null)[] }) {
  // values are newest-first; plot oldest -> newest.
  const pts = [...values].reverse();
  const nums = pts.filter((v): v is number => v != null);
  if (nums.length < 2) return <span className="text-ink-faint">—</span>;
  const min = Math.min(...nums), max = Math.max(...nums);
  const span = max - min || 1;
  const w = 56, h = 16;
  const step = w / (pts.length - 1);
  let last = nums[0];
  const d = pts.map((v, i) => {
    const y = h - (((v ?? last) - min) / span) * h;
    if (v != null) last = v;
    return `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const up = (nums[nums.length - 1] ?? 0) >= (nums[0] ?? 0);
  return (
    <svg width={w} height={h} className="inline-block align-middle">
      <path d={d} fill="none" stroke={up ? "#F6465D" : "#2EBD85"} strokeWidth="1.2" />
    </svg>
  );
}

function StatementTable({ stmt, currency }: { stmt: Statement; currency: string | null }) {
  if (!stmt.rows.length) return <p className="text-sm text-ink-faint py-6 text-center">暂无该报表数据。</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] text-ink-faint border-b border-line">
            <th className="text-left font-medium py-2 pr-3 sticky left-0 bg-base">科目{currency ? ` (${currency})` : ""}</th>
            <th className="text-right font-medium px-2">趋势</th>
            {stmt.periods.map((p) => <th key={p} className="text-right font-medium px-3 whitespace-nowrap">{p}</th>)}
          </tr>
        </thead>
        <tbody>
          {stmt.rows.map((r) => (
            <tr key={r.label} className="border-b border-line/50 hover:bg-panel-2/40">
              <td className="py-1.5 pr-3 text-ink-dim whitespace-nowrap sticky left-0 bg-base">{r.label}</td>
              <td className="px-2 text-right"><Spark values={r.values} /></td>
              {r.values.map((v, i) => (
                <td key={i} className="text-right tnum px-3 text-ink whitespace-nowrap">
                  {isPerShare(r.label) ? num(v) : compact(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Assumption({ label, value, onChange, suffix, step, min, max }: {
  label: string; value: number; onChange: (v: number) => void;
  suffix?: string; step: number; min: number; max: number;
}) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-ink-dim">{label}</span>
        <span className="tnum text-ink">{value}{suffix}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-accent" />
    </div>
  );
}

export default function DeepResearch({ symbol }: { symbol: string }) {
  const [fin, setFin] = useState<Financials | null>(null);
  const [tab, setTab] = useState<StmtKey>("income");
  const [quarterly, setQuarterly] = useState(false);
  const [loading, setLoading] = useState(true);

  // DCF assumptions (percent units in the UI; converted to fractions for the API).
  const [dcf, setDcf] = useState<DcfView | null>(null);
  const [growth, setGrowth] = useState<number | null>(null); // %
  const [discount, setDiscount] = useState(9); // %
  const [terminal, setTerminal] = useState(2.5); // %
  const [years, setYears] = useState(5);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    setLoading(true); setFin(null); setDcf(null); setSeeded(false);
    getFinancials(symbol).then(setFin).catch(() => setFin(null)).finally(() => setLoading(false));
  }, [symbol]);

  // First DCF call (no params) seeds the sliders with the server's defaults.
  useEffect(() => {
    getDcf(symbol).then((v) => {
      setDcf(v);
      if (v.result && !seeded) {
        setGrowth(Math.round(v.result.growth * 1000) / 10);
        setDiscount(Math.round(v.result.discount * 1000) / 10);
        setTerminal(Math.round(v.result.terminal_growth * 1000) / 10);
        setYears(v.result.years);
        setSeeded(true);
      }
    }).catch(() => setDcf(null));
  }, [symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  const recompute = useCallback(() => {
    if (growth == null) return;
    getDcf(symbol, {
      growth: growth / 100, discount: discount / 100, terminal: terminal / 100, years,
    }).then(setDcf).catch(() => {});
  }, [symbol, growth, discount, terminal, years]);

  useEffect(() => {
    if (seeded) recompute();
  }, [seeded, growth, discount, terminal, years, recompute]);

  const stmt: Statement | null = useMemo(() => {
    if (!fin) return null;
    const k = (quarterly ? `${tab}_q` : tab) as keyof Financials;
    return (fin[k] as Statement) ?? null;
  }, [fin, tab, quarterly]);

  const res = dcf?.result ?? null;
  const upTone = (dcf?.upside_pct ?? 0) >= 0 ? "text-up" : "text-down";

  return (
    <div className="flex-1 min-w-0 overflow-auto p-5 space-y-5">
      <div className="flex items-baseline gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{symbol}</h1>
        <span className="text-sm text-ink-dim">深度研究 · 财报 + DCF 估值</span>
      </div>

      {/* Financial statements */}
      <Panel title="财务报表" hint={fin?.currency ?? undefined}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex gap-1">
            {STMT_TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  tab === t.key ? "bg-panel-2 text-ink border border-line" : "text-ink-dim hover:text-ink"
                }`}>{t.label}</button>
            ))}
          </div>
          <div className="flex gap-1 text-xs">
            <button onClick={() => setQuarterly(false)}
              className={`px-2.5 py-1 rounded ${!quarterly ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink"}`}>年度</button>
            <button onClick={() => setQuarterly(true)}
              className={`px-2.5 py-1 rounded ${quarterly ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink"}`}>季度</button>
          </div>
        </div>
        {loading ? <p className="text-sm text-ink-faint py-6 text-center">加载中…</p>
          : stmt ? <StatementTable stmt={stmt} currency={fin?.currency ?? null} />
          : <p className="text-sm text-ink-faint py-6 text-center">暂无财报数据。请先在自选「全部更新」或确认该标的有公开财报。</p>}
      </Panel>

      {/* DCF */}
      <Panel title="DCF 估值" hint="两阶段折现自由现金流">
        {dcf && dcf.has_fcf === false ? (
          <p className="text-sm text-ink-faint py-4">该标的缺少足够的自由现金流 / 股本数据,暂不能做 DCF 估值。</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Assumptions */}
            <div className="space-y-4">
              <Assumption label="自由现金流年增长率" value={growth ?? 8} onChange={setGrowth} suffix="%" step={0.5} min={-10} max={40} />
              <Assumption label="折现率 (WACC)" value={discount} onChange={setDiscount} suffix="%" step={0.5} min={4} max={20} />
              <Assumption label="永续增长率" value={terminal} onChange={setTerminal} suffix="%" step={0.5} min={0} max={6} />
              <Assumption label="预测年限" value={years} onChange={(v) => setYears(Math.round(v))} suffix=" 年" step={1} min={3} max={10} />
              <p className="text-[11px] text-ink-faint pt-1">默认增长率由历史 FCF 复合增速推算;数字均为确定性计算,非投资建议。</p>
            </div>

            {/* Result */}
            <div className="space-y-3">
              <div className="rounded-lg border border-line bg-panel p-4">
                <div className="text-xs text-ink-faint mb-1">每股内在价值</div>
                <div className="text-3xl font-semibold tnum">
                  {res?.intrinsic_per_share != null ? num(res.intrinsic_per_share) : "—"}
                  <span className="text-sm text-ink-dim ml-1">{dcf?.currency ?? ""}</span>
                </div>
                <div className="flex items-center gap-3 mt-2 text-sm">
                  <span className="text-ink-dim">现价 <span className="tnum text-ink">{num(dcf?.price)}</span></span>
                  <span className={`tnum ${upTone}`}>
                    {dcf?.upside_pct != null ? `${dcf.upside_pct >= 0 ? "低估" : "高估"} ${signedPct(dcf.upside_pct)}` : "—"}
                  </span>
                </div>
              </div>
              {res && (
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <Mini label="企业价值" v={compact(res.enterprise_value)} />
                  <Mini label="股权价值" v={compact(res.equity_value)} />
                  <Mini label="终值现值" v={compact(res.pv_terminal)} />
                  <Mini label="净负债" v={compact(res.net_debt)} />
                </div>
              )}
            </div>
          </div>
        )}

        {res && res.table.length > 0 && (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-ink-faint border-b border-line">
                  <th className="text-left font-medium py-1.5">预测年</th>
                  {res.table.map((y) => <th key={y.year} className="text-right font-medium px-3">第{y.year}年</th>)}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-line/50">
                  <td className="py-1.5 text-ink-dim">预测 FCF</td>
                  {res.table.map((y) => <td key={y.year} className="text-right tnum px-3 text-ink">{compact(y.fcf)}</td>)}
                </tr>
                <tr>
                  <td className="py-1.5 text-ink-dim">折现现值</td>
                  {res.table.map((y) => <td key={y.year} className="text-right tnum px-3 text-ink-dim">{compact(y.pv)}</td>)}
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

function Mini({ label, v }: { label: string; v: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-3 py-2">
      <div className="text-ink-faint">{label}</div>
      <div className="tnum text-ink mt-0.5">{v}</div>
    </div>
  );
}
