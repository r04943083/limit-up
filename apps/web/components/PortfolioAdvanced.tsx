"use client";

import { useEffect, useState } from "react";
import Panel from "@/components/Panel";
import {
  getOptimize, getAttribution, getTlh,
  type OptimizeResult, type AttributionResult, type TlhServiceResult,
} from "@/lib/api";
import { compact, signedPct, dirClass, errText } from "@/lib/format";

const METHODS: { key: string; label: string }[] = [
  { key: "max_sharpe", label: "最大夏普" },
  { key: "min_variance", label: "最小方差" },
  { key: "risk_parity", label: "风险平价" },
  { key: "black_litterman", label: "Black-Litterman" },
];

// Phase 6 advanced analytics: optimizer + Brinson attribution + tax-loss harvesting.
export default function PortfolioAdvanced({ pid }: { pid: number }) {
  return (
    <>
      <OptimizerPanel pid={pid} />
      <AttributionPanel pid={pid} />
      <TlhPanel pid={pid} />
    </>
  );
}

function OptimizerPanel({ pid }: { pid: number }) {
  const [method, setMethod] = useState("max_sharpe");
  const [data, setData] = useState<OptimizeResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setData(null); setErr(null);
    getOptimize(pid, method).then(setData).catch((e) => setErr(errText(e)));
  }, [pid, method]);

  const w = data?.weights;
  return (
    <Panel title="组合优化" hint={w?.expected_return_pct != null ? `预期年化 ${w.expected_return_pct}% · 波动 ${w.volatility_pct}% · Sharpe ${w.sharpe}` : "整数股分配"}>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {METHODS.map((m) => (
          <button key={m.key} onClick={() => setMethod(m.key)}
            className={`px-2.5 py-1 rounded text-xs ${m.key === method ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink border border-line"}`}>
            {m.label}
          </button>
        ))}
      </div>
      {err ? <p className="text-sm text-ink-faint py-4 text-center">{err}</p>
        : !data ? <p className="text-sm text-ink-faint py-4 text-center">优化中…</p>
        : !data.ok || !w ? <p className="text-sm text-ink-faint py-4 text-center">{data.error === "need at least 2 holdings" ? "至少需要 2 个持仓。" : "价格历史不足。"}</p>
        : (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-ink-faint border-b border-line">
                  <th className="text-left font-normal py-1.5">标的</th>
                  <th className="text-right font-normal">当前</th>
                  <th className="text-right font-normal">目标</th>
                  <th className="text-right font-normal">建议买入</th>
                </tr>
              </thead>
              <tbody>
                {w.symbols.map((s, i) => {
                  const cur = (data.current_weights[s] ?? 0) * 100;
                  const tgt = w.weights[i] * 100;
                  const alloc = data.plan?.allocations.find((a) => a.symbol === s);
                  return (
                    <tr key={s} className="border-b border-line/50">
                      <td className="py-1.5 font-medium text-accent">{s}</td>
                      <td className="py-1.5 text-right tabular-nums text-ink-dim">{cur.toFixed(1)}%</td>
                      <td className="py-1.5 text-right tabular-nums">{tgt.toFixed(1)}%</td>
                      <td className="py-1.5 text-right tabular-nums text-ink-dim">{alloc ? `${alloc.shares} 股` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {w.note && <p className="mt-2 text-[11px] text-warn">{w.note}</p>}
            {data.plan && (
              <p className="mt-2 text-[11px] text-ink-faint">
                按 {compact(data.plan.capital)} 资金整数股分配 · 剩余现金 {compact(data.plan.leftover_cash)}
              </p>
            )}
          </div>
        )}
    </Panel>
  );
}

function AttributionPanel({ pid }: { pid: number }) {
  const [data, setData] = useState<AttributionResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setData(null); setErr(null);
    getAttribution(pid).then(setData).catch((e) => setErr(errText(e)));
  }, [pid]);

  const a = data?.attribution;
  return (
    <Panel title="业绩归因 (Brinson)" hint={a ? `vs ${a.benchmark} · 超额 ${signedPct(a.total_active_pct)}` : "配置 / 选股 / 交互"}>
      {err ? <p className="text-sm text-ink-faint py-4 text-center">{err}</p>
        : !data ? <p className="text-sm text-ink-faint py-4 text-center">归因中…</p>
        : !data.ok || !a ? <p className="text-sm text-ink-faint py-4 text-center">至少需要 2 个持仓且有价格历史。</p>
        : (
          <>
            <div className="flex flex-wrap gap-4 mb-3 text-sm">
              <span>配置效应 <b className={dirClass(a.allocation_pct)}>{signedPct(a.allocation_pct)}</b></span>
              <span>选股效应 <b className={dirClass(a.selection_pct)}>{signedPct(a.selection_pct)}</b></span>
              <span>交互效应 <b className={dirClass(a.interaction_pct)}>{signedPct(a.interaction_pct)}</b></span>
              <span className="ml-auto text-ink-dim">组合 {signedPct(a.port_return_pct)} · 基准 {signedPct(a.bench_return_pct)}</span>
            </div>
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-ink-faint border-b border-line">
                    <th className="text-left font-normal py-1.5">板块</th>
                    <th className="text-right font-normal">权重(组/基)</th>
                    <th className="text-right font-normal">收益(组/基)</th>
                    <th className="text-right font-normal">配置</th>
                    <th className="text-right font-normal">选股</th>
                  </tr>
                </thead>
                <tbody>
                  {a.segments.map((s) => (
                    <tr key={s.segment} className="border-b border-line/50">
                      <td className="py-1.5">{s.segment}</td>
                      <td className="py-1.5 text-right tabular-nums text-ink-dim">{s.port_weight}/{s.bench_weight}%</td>
                      <td className="py-1.5 text-right tabular-nums text-ink-dim">{s.port_return_pct}/{s.bench_return_pct}%</td>
                      <td className={`py-1.5 text-right tabular-nums ${dirClass(s.allocation)}`}>{signedPct(s.allocation)}</td>
                      <td className={`py-1.5 text-right tabular-nums ${dirClass(s.selection)}`}>{signedPct(s.selection)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
    </Panel>
  );
}

function TlhPanel({ pid }: { pid: number }) {
  const [data, setData] = useState<TlhServiceResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setData(null); setErr(null);
    getTlh(pid).then(setData).catch((e) => setErr(errText(e)));
  }, [pid]);

  const cands = data?.result.candidates ?? [];
  return (
    <Panel title="税损收割 (TLH)" hint={data?.ok ? `可收割浮亏 ${compact(data.result.total_harvestable_loss)}` : "浮亏持仓 + 洗售规则"}>
      {err ? <p className="text-sm text-ink-faint py-4 text-center">{err}</p>
        : !data ? <p className="text-sm text-ink-faint py-4 text-center">扫描中…</p>
        : cands.length === 0 ? <p className="text-sm text-ink-faint py-4 text-center">当前无浮亏持仓可收割。</p>
        : (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-ink-faint border-b border-line">
                  <th className="text-left font-normal py-1.5">标的</th>
                  <th className="text-right font-normal">成本 / 现价</th>
                  <th className="text-right font-normal">浮亏</th>
                  <th className="text-right font-normal">幅度</th>
                  <th className="text-left font-normal pl-3">洗售</th>
                </tr>
              </thead>
              <tbody>
                {cands.map((c) => (
                  <tr key={c.symbol} className="border-b border-line/50">
                    <td className="py-1.5 font-medium text-accent">{c.symbol}</td>
                    <td className="py-1.5 text-right tabular-nums text-ink-dim">{c.avg_cost} / {c.price}</td>
                    <td className="py-1.5 text-right tabular-nums text-down">-{compact(c.unrealized_loss)}</td>
                    <td className="py-1.5 text-right tabular-nums text-down">{c.loss_pct}%</td>
                    <td className="py-1.5 pl-3">{c.wash_sale_risk ? <span className="text-warn text-[11px]" title={c.note ?? ""}>需注意</span> : <span className="text-ink-faint text-[11px]">可收割</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </Panel>
  );
}
