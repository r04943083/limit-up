"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import { Stat, RecBadge, Chip } from "@/components/ui";
import {
  getPortfolio, importPortfolioCsv, addHolding, removeHolding,
  getAnalytics, getReview, runReview,
  type PortfolioAnalytics, type PortfolioReview,
} from "@/lib/api";
import { num, compact, signedPct } from "@/lib/format";

const ALLOC_COLORS = ["#21D0C3", "#E0A33E", "#9B7BE6", "#22C55E", "#EF4444", "#5B9BD5", "#E06AAA"];

function AllocBars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <div className="space-y-2">
      {entries.map(([k, v], i) => (
        <div key={k}>
          <div className="flex justify-between text-xs mb-0.5">
            <span className="text-ink-dim">{k}</span>
            <span className="tnum text-ink-faint">{(v * 100).toFixed(1)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-panel-2 overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${v * 100}%`, background: ALLOC_COLORS[i % ALLOC_COLORS.length] }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function CorrelationHeatmap({ symbols, matrix }: { symbols: string[]; matrix: (number | null)[][] }) {
  // 红 = 正相关(齐涨齐跌,集中风险);绿 = 负相关(分散对冲)。透明度随相关性强弱。
  const cell = (v: number | null) => {
    if (v == null) return { background: "transparent", color: "var(--ink-faint, #8B98A5)" };
    const a = Math.min(1, Math.abs(v)) * 0.85;
    const bg = v >= 0 ? `rgba(246,70,93,${a})` : `rgba(46,189,133,${a})`;
    return { background: bg, color: Math.abs(v) > 0.5 ? "#fff" : "inherit" };
  };
  return (
    <div className="overflow-x-auto">
      <table className="text-[11px] tnum border-collapse">
        <thead>
          <tr>
            <th className="p-1"></th>
            {symbols.map((s) => <th key={s} className="p-1 text-ink-faint font-medium whitespace-nowrap">{s}</th>)}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={symbols[i]}>
              <td className="p-1 text-ink-faint font-medium whitespace-nowrap pr-2">{symbols[i]}</td>
              {row.map((v, j) => (
                <td key={j} className="p-1 text-center rounded" style={{ ...cell(v), minWidth: 38 }}>
                  {v == null ? "—" : v.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PortfolioPage() {
  const [pid, setPid] = useState<number | null>(null);
  const [a, setA] = useState<PortfolioAnalytics | null>(null);
  const [review, setReview] = useState<PortfolioReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [sym, setSym] = useState("");
  const [qty, setQty] = useState("");
  const [cost, setCost] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const loadAnalytics = useCallback((id: number) => {
    setA(null);
    getAnalytics(id).then(setA).catch((e) => setMsg(String(e)));
  }, []);

  useEffect(() => {
    getPortfolio().then((p) => {
      setPid(p.id);
      if (p.holdings.length) loadAnalytics(p.id);
      getReview(p.id).then(setReview).catch(() => {});
    });
  }, [loadAnalytics]);

  const add = async () => {
    if (!pid || !sym.trim()) return;
    setBusy(true);
    try {
      await addHolding(pid, sym.trim().toUpperCase(), Number(qty) || 0, cost ? Number(cost) : undefined);
      setSym(""); setQty(""); setCost("");
      loadAnalytics(pid);
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };

  const onFile = async (file: File) => {
    if (!pid) return;
    setBusy(true);
    try {
      const { added } = await importPortfolioCsv(pid, await file.text());
      setMsg(`已导入 ${added} 个持仓。`);
      loadAnalytics(pid);
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };

  const doReview = () => {
    if (!pid) return;
    setReviewing(true);
    runReview(pid).then(setReview).catch((e) => setMsg(String(e))).finally(() => setReviewing(false));
  };

  const effNames = a && a.hhi > 0 ? 1 / a.hhi : null;

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div className="flex items-baseline justify-between">
        <h1 className="text-xl font-semibold tracking-tight">组合</h1>
        {a && (
          <div className="text-right">
            <div className="text-2xl font-semibold tnum">
              {compact(a.total_value)} <span className="text-sm text-ink-dim">{a.base_currency}</span>
            </div>
            <div className={`text-sm tnum ${(a.total_pnl_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>
              {signedPct(a.total_pnl_pct)} · {a.total_pnl >= 0 ? "+" : ""}{compact(a.total_pnl)}
            </div>
          </div>
        )}
      </div>

      <Panel title="新增 / 导入持仓" hint="CSV 列:symbol, quantity, avg_cost">
        <div className="flex flex-wrap gap-2">
          <input value={sym} onChange={(e) => setSym(e.target.value)} placeholder="代码"
            className="w-32 bg-base border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/60" />
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="数量"
            className="w-24 bg-base border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/60" />
          <input value={cost} onChange={(e) => setCost(e.target.value)} placeholder="成本价"
            className="w-28 bg-base border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/60" />
          <button onClick={add} disabled={busy}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 hover:bg-accent/25 disabled:opacity-50">加入</button>
          <button onClick={() => fileRef.current?.click()} disabled={busy}
            className="rounded-lg border border-line text-ink-dim text-sm px-4 hover:text-ink disabled:opacity-50">导入 CSV</button>
          <input ref={fileRef} type="file" accept=".csv,text/csv,text/plain" className="hidden"
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
        </div>
        {msg && <p className="text-xs text-ink-faint mt-2">{msg}</p>}
      </Panel>

      {a && a.positions.length > 0 && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Panel title="行业分布"><AllocBars data={a.sector_alloc} /></Panel>
            <Panel title="市场分布"><AllocBars data={a.market_alloc} /></Panel>
            <Panel title="风险与集中度">
              <Stat label="总成本" value={compact(a.total_cost)} />
              <Stat label="浮动盈亏" value={signedPct(a.total_pnl_pct)} tone={(a.total_pnl_pct ?? 0) >= 0 ? "up" : "down"} />
              <Stat label="第一大持仓" value={`${(a.top_weight * 100).toFixed(1)}%`} />
              <Stat label="集中度 (HHI)" value={a.hhi.toFixed(3)} />
              <Stat label="有效持仓数" value={effNames ? effNames.toFixed(1) : "—"} />
            </Panel>
          </div>

          <Panel title="持仓明细" hint={`${a.positions.length}`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-ink-faint border-b border-line">
                  <th className="text-left font-medium py-2">代码</th>
                  <th className="text-right font-medium">数量</th>
                  <th className="text-right font-medium">成本价</th>
                  <th className="text-right font-medium">现价</th>
                  <th className="text-right font-medium">市值</th>
                  <th className="text-right font-medium">权重</th>
                  <th className="text-right font-medium">盈亏</th>
                </tr>
              </thead>
              <tbody>
                {a.positions.map((p) => (
                  <tr key={p.symbol} className="border-b border-line/60 hover:bg-panel-2/40">
                    <td className="py-2">
                      <Link href={`/research/${encodeURIComponent(p.symbol)}`} className="text-accent font-medium">{p.symbol}</Link>
                      <span className="text-ink-faint text-xs ml-2">{p.sector ?? ""}</span>
                    </td>
                    <td className="text-right tnum text-ink-dim">{num(p.quantity, 0)}</td>
                    <td className="text-right tnum text-ink-dim">{num(p.avg_cost)}</td>
                    <td className="text-right tnum text-ink-dim">{num(p.price)}</td>
                    <td className="text-right tnum">{compact(p.market_value)}</td>
                    <td className="text-right tnum text-ink-dim">{(p.weight * 100).toFixed(1)}%</td>
                    <td className={`text-right tnum ${(p.pnl_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>{signedPct(p.pnl_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {a.correlation_symbols.length > 1 && (
            <Panel title="持仓相关性" hint="红=正相关(集中) · 绿=负相关(分散)">
              <CorrelationHeatmap symbols={a.correlation_symbols} matrix={a.correlation_matrix} />
            </Panel>
          )}
        </>
      )}

      <Panel title="AI 组合点评" hint="claude -p">
        <button onClick={doReview} disabled={reviewing || !a}
          className="w-full mb-3 rounded-lg bg-accent/15 text-accent text-sm font-medium py-2 hover:bg-accent/25 disabled:opacity-50">
          {reviewing ? "点评中…(约 30–60 秒)" : review ? "重新点评" : "AI 点评组合"}
        </button>
        {review ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-ink-faint">风险等级:</span>
              <RecBadge rec={review.risk_level} tone={review.risk_level === "low" ? "up" : review.risk_level === "high" ? "down" : "amber"} />
            </div>
            <p className="text-sm text-ink-dim leading-relaxed">{review.summary}</p>
            {review.concerns.length > 0 && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">关注点</div>
                <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">
                  {review.concerns.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
            {review.suggestions.length > 0 && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">建议</div>
                <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">
                  {review.suggestions.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
            <p className="text-[11px] text-ink-faint">AI 观点 · 非投资建议</p>
          </div>
        ) : (
          <p className="text-sm text-ink-faint">先导入持仓,再让 AI 点评集中度、行业偏向与风险。</p>
        )}
      </Panel>

      {(!a || a.positions.length === 0) && (
        <p className="text-sm text-ink-faint flex items-center gap-2">
          还没有持仓。在上方新增,或导入 CSV。<Chip>支持富途 / IBKR 导出</Chip>
        </p>
      )}
    </div>
  );
}
