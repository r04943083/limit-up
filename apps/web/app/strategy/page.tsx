"use client";

import { useEffect, useMemo, useState } from "react";
import Panel from "@/components/Panel";
import SymbolInput from "@/components/SymbolInput";
import { Stat } from "@/components/ui";
import {
  explainBacktest, getStrategyKinds, runBacktest,
  type BacktestResult, type StrategyRead, type StrategySpec,
} from "@/lib/api";
import { dirClass, num, pct } from "@/lib/format";

const KIND_LABEL: Record<string, string> = {
  rsi: "RSI 超买超卖", ma_cross: "均线交叉", breakout: "突破/海龟",
};

function EquityChart({ result }: { result: BacktestResult }) {
  const { d1, d2, w, h } = useMemo(() => {
    const c = result.curve;
    if (c.length < 2) return { d1: "", d2: "", w: 600, h: 200 };
    const W = 600, H = 200, pad = 4;
    const eqs = c.map((p) => p.equity);
    const bhs = c.map((p) => p.buy_hold);
    const lo = Math.min(...eqs, ...bhs), hi = Math.max(...eqs, ...bhs);
    const span = hi - lo || 1;
    const x = (i: number) => pad + (i / (c.length - 1)) * (W - 2 * pad);
    const y = (v: number) => H - pad - ((v - lo) / span) * (H - 2 * pad);
    const path = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
    return { d1: path(eqs), d2: path(bhs), w: W, h: H };
  }, [result]);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48" preserveAspectRatio="none">
      <path d={d2} fill="none" stroke="#5B6672" strokeWidth="1.5" strokeDasharray="4 3" />
      <path d={d1} fill="none" stroke="#21D0C3" strokeWidth="2" />
    </svg>
  );
}

export default function StrategyPage() {
  const [kinds, setKinds] = useState<string[]>([]);
  const [symbol, setSymbol] = useState("NVDA");
  const [spec, setSpec] = useState<StrategySpec>({
    kind: "ma_cross", fast: 20, slow: 50, rsi_period: 14, rsi_buy: 30, rsi_sell: 70,
    lookback: 20, exit_lookback: 10, starting_cash: 10000,
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [read, setRead] = useState<StrategyRead | null>(null);
  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { getStrategyKinds().then(setKinds).catch(() => {}); }, []);

  const run = () => {
    if (!symbol.trim()) return;
    setBusy(true); setErr(null); setRead(null);
    runBacktest(symbol.trim().toUpperCase(), spec)
      .then(setResult)
      .catch((e) => setErr(String(e).replace(/^Error:\s*/, "")))
      .finally(() => setBusy(false));
  };

  const explain = () => {
    if (!result) return;
    setReading(true);
    // Explain the spec that PRODUCED the shown result, not the live-edited `spec` — otherwise
    // the AI narrates a different strategy than the equity curve/stats on screen.
    explainBacktest(result.symbol, result.spec)
      .then(setRead).catch((e) => setErr(String(e))).finally(() => setReading(false));
  };

  const s = result?.stats;
  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">策略构建器</h1>
        <p className="text-sm text-ink-dim">规则化策略 · 历史回测(确定性计算)· AI 仅解读结果</p>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      <Panel title="策略参数" hint="设置后回测">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <SymbolInput value={symbol} onChange={setSymbol} />
          <select value={spec.kind} onChange={(e) => setSpec({ ...spec, kind: e.target.value })}
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent">
            {kinds.map((k) => <option key={k} value={k}>{KIND_LABEL[k] ?? k}</option>)}
          </select>
          {spec.kind === "ma_cross" && (<>
            <NumIn label="快线" v={spec.fast!} set={(v) => setSpec({ ...spec, fast: v })} />
            <NumIn label="慢线" v={spec.slow!} set={(v) => setSpec({ ...spec, slow: v })} />
          </>)}
          {spec.kind === "rsi" && (<>
            <NumIn label="买入 RSI<" v={spec.rsi_buy!} set={(v) => setSpec({ ...spec, rsi_buy: v })} />
            <NumIn label="卖出 RSI>" v={spec.rsi_sell!} set={(v) => setSpec({ ...spec, rsi_sell: v })} />
          </>)}
          {spec.kind === "breakout" && (<>
            <NumIn label="突破回看" v={spec.lookback!} set={(v) => setSpec({ ...spec, lookback: v })} />
            <NumIn label="离场回看" v={spec.exit_lookback!} set={(v) => setSpec({ ...spec, exit_lookback: v })} />
          </>)}
        </div>
        <div className="mt-3 flex justify-end">
          <button onClick={run} disabled={busy || !symbol.trim()}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40">
            {busy ? "回测中…" : "运行回测"}
          </button>
        </div>
      </Panel>

      {result && s && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Panel title="净值曲线" hint={`${result.bars} 根K线`} className="lg:col-span-2">
            <EquityChart result={result} />
            <div className="flex gap-4 mt-2 text-xs">
              <span className="text-accent">— 策略</span>
              <span className="text-ink-faint">┄ 买入持有</span>
            </div>
          </Panel>
          <Panel title="回测统计" hint={result.symbol}>
            <Stat label="策略收益" value={<span className={dirClass(s.total_return_pct)}>{pct(s.total_return_pct)}</span>} />
            <Stat label="买入持有" value={<span className={dirClass(s.buy_hold_return_pct)}>{pct(s.buy_hold_return_pct)}</span>} />
            <Stat label="年化 CAGR" value={pct(s.cagr_pct)} />
            <Stat label="最大回撤" value={<span className="text-down">{pct(s.max_drawdown_pct)}</span>} />
            <Stat label="胜率" value={pct(s.win_rate)} />
            <Stat label="交易次数" value={String(s.trades)} />
            <Stat label="Sharpe" value={s.sharpe == null ? "—" : num(s.sharpe)} />
            <Stat label="持仓占比" value={pct(s.exposure_pct)} />
            <button onClick={explain} disabled={reading}
              className="mt-3 w-full rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40">
              {reading ? "AI 解读中…" : "AI 解读回测"}
            </button>
          </Panel>
        </div>
      )}

      {read && (
        <Panel title="AI 解读" hint={read.verdict}>
          <p className="text-sm text-ink leading-relaxed">{read.summary}</p>
          {read.observations.length > 0 && (
            <ul className="mt-2 text-sm text-ink-dim list-disc pl-5 space-y-1">
              {read.observations.map((o, i) => <li key={i}>{o}</li>)}
            </ul>
          )}
          {read.cautions.length > 0 && (
            <p className="mt-2 text-xs text-warn">注意:{read.cautions.join("、")}</p>
          )}
          <p className="text-[11px] text-ink-faint mt-2">AI 观点 · 非投资建议</p>
        </Panel>
      )}
    </div>
  );
}

function NumIn({ label, v, set }: { label: string; v: number; set: (v: number) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] text-ink-faint">{label}</span>
      <input value={v} onChange={(e) => set(Number(e.target.value) || 0)} inputMode="decimal"
        className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent tnum" />
    </label>
  );
}
