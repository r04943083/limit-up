"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import { getPaper, paperTrade, resetPaper, type PaperAccount } from "@/lib/api";
import { dirClass, num, pct, sinceLabel } from "@/lib/format";

export default function PaperPage() {
  const [acct, setAcct] = useState<PaperAccount | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ symbol: "", side: "buy" as "buy" | "sell", quantity: "" });

  const load = useCallback(() => {
    getPaper().then(setAcct).catch((e) => setErr(String(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  const doTrade = () => {
    const qty = Number(form.quantity);
    if (!form.symbol.trim() || !qty || qty <= 0) return;
    setBusy(true);
    setErr(null);
    paperTrade(form.symbol.trim().toUpperCase(), form.side, qty)
      .then((a) => { setAcct(a); setForm({ ...form, quantity: "" }); })
      .catch((e) => setErr(String(e).replace(/^Error:\s*/, "")))
      .finally(() => setBusy(false));
  };

  const reset = () => {
    if (!confirm("重置模拟账户?将清空所有持仓与交易记录。")) return;
    resetPaper().then(setAcct).catch((e) => setErr(String(e)));
  };

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">模拟交易</h1>
          <p className="text-sm text-ink-dim">用缓存价格虚拟买卖 · 持仓与盈亏实时计算(红涨绿跌)</p>
        </div>
        <button onClick={reset} className="rounded-lg border border-line text-ink-dim text-sm px-3 py-1.5 hover:text-ink">
          重置账户
        </button>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      {acct && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Panel title="总资产"><p className="text-2xl font-semibold tnum">{num(acct.equity)}</p>
            <p className="text-xs text-ink-faint mt-1">初始 {num(acct.starting_cash, 0)}</p></Panel>
          <Panel title="现金"><p className="text-2xl font-semibold tnum">{num(acct.cash)}</p>
            <p className="text-xs text-ink-faint mt-1">已投入 {num(acct.invested)}</p></Panel>
          <Panel title="总盈亏"><p className={`text-2xl font-semibold tnum ${dirClass(acct.total_pnl)}`}>{num(acct.total_pnl)}</p>
            <p className={`text-xs mt-1 tnum ${dirClass(acct.total_return_pct)}`}>{pct(acct.total_return_pct)}</p></Panel>
          <Panel title="持仓数"><p className="text-2xl font-semibold tnum">{acct.positions.length}</p>
            <p className="text-xs text-ink-faint mt-1">交易 {acct.trades.length} 笔</p></Panel>
        </div>
      )}

      <Panel title="下单" hint="按缓存价成交">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })}
            placeholder="代码 如 NVDA"
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
          <select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value as "buy" | "sell" })}
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent">
            <option value="buy">买入</option>
            <option value="sell">卖出</option>
          </select>
          <input value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            placeholder="数量" inputMode="decimal"
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
          <button onClick={doTrade} disabled={busy || !form.symbol.trim() || !Number(form.quantity)}
            className={`rounded-lg text-sm font-medium px-4 py-2 disabled:opacity-40 ${
              form.side === "buy" ? "bg-up/15 text-up hover:bg-up/25" : "bg-down/15 text-down hover:bg-down/25"
            }`}>
            {busy ? "成交中…" : form.side === "buy" ? "买入" : "卖出"}
          </button>
        </div>
        <p className="text-[11px] text-ink-faint mt-2">提示:需先在自选/研究里同步过该标的(有缓存价)才能成交。</p>
      </Panel>

      <Panel title="持仓" hint={acct ? `${acct.positions.length} 只` : ""}>
        {acct && acct.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-ink-faint text-xs border-b border-line">
                  <th className="text-left py-2 font-normal">代码</th>
                  <th className="text-right font-normal">数量</th>
                  <th className="text-right font-normal">成本</th>
                  <th className="text-right font-normal">现价</th>
                  <th className="text-right font-normal">市值</th>
                  <th className="text-right font-normal">盈亏</th>
                  <th className="text-right font-normal">收益率</th>
                  <th className="text-right font-normal">仓位</th>
                </tr>
              </thead>
              <tbody>
                {acct.positions.map((p) => (
                  <tr key={p.symbol} className="border-b border-line/50">
                    <td className="py-2"><Link href={`/research/${p.symbol}`} className="text-accent">{p.symbol}</Link></td>
                    <td className="text-right tnum">{num(p.quantity, 2)}</td>
                    <td className="text-right tnum">{num(p.avg_cost)}</td>
                    <td className="text-right tnum">{num(p.price)}</td>
                    <td className="text-right tnum">{num(p.market_value)}</td>
                    <td className={`text-right tnum ${dirClass(p.pnl)}`}>{num(p.pnl)}</td>
                    <td className={`text-right tnum ${dirClass(p.pnl_pct)}`}>{pct(p.pnl_pct)}</td>
                    <td className="text-right tnum text-ink-dim">{pct(p.weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-faint">还没有持仓。在上方下单建立第一笔模拟交易。</p>
        )}
      </Panel>

      {acct && acct.trades.length > 0 && (
        <Panel title="成交记录" hint={`${acct.trades.length} 笔`}>
          <div className="space-y-1">
            {acct.trades.slice(0, 30).map((t) => (
              <div key={t.id} className="flex items-center justify-between text-sm py-1.5 border-b border-line/40 last:border-0">
                <div className="flex items-center gap-2">
                  <span className={t.side === "buy" ? "text-up" : "text-down"}>{t.side === "buy" ? "买" : "卖"}</span>
                  <span className="text-ink">{t.symbol}</span>
                  <span className="text-ink-dim tnum">{num(t.quantity, 2)} @ {num(t.price)}</span>
                </div>
                <span className="text-xs text-ink-faint">{sinceLabel(t.created_at)}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
