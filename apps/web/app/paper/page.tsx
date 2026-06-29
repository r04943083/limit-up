"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import MultiLineChart, { type Series } from "@/components/MultiLineChart";
import {
  getPaper, paperTrade, resetPaper, getArena, arenaTick, resetArena,
  type PaperAccount, type ArenaOut, type ArenaAgent,
} from "@/lib/api";
import { dirClass, num, pct, signedPct, sinceLabel } from "@/lib/format";

const AGENT_COLORS = ["#F6465D", "#21D0C3", "#E0A33E", "#9B7BE6", "#5B9BD5", "#E06AAA"];

export default function PaperPage() {
  const [tab, setTab] = useState<"arena" | "manual">("arena");
  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">模拟交易</h1>
          <p className="text-sm text-ink-dim">
            {tab === "arena"
              ? "AI 竞技场 · 多位投资人格各管一个组合,按各自风格自动操盘,比拼收益(红涨绿跌)"
              : "你自己的模拟盘 · 用缓存价格虚拟买卖,持仓与盈亏实时计算"}
          </p>
        </div>
        <div className="flex rounded-lg border border-line overflow-hidden text-sm shrink-0">
          <button onClick={() => setTab("arena")}
            className={`px-4 py-1.5 ${tab === "arena" ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink"}`}>
            AI 竞技场
          </button>
          <button onClick={() => setTab("manual")}
            className={`px-4 py-1.5 border-l border-line ${tab === "manual" ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink"}`}>
            我的模拟盘
          </button>
        </div>
      </div>
      {tab === "arena" ? <Arena /> : <Manual />}
    </div>
  );
}

/* ----------------------------------------------------------------- AI 竞技场 */
function Arena() {
  const [data, setData] = useState<ArenaOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => { getArena().then(setData).catch((e) => setMsg(String(e))); }, []);
  useEffect(() => {
    load();
    window.addEventListener("lu:synced", load);
    return () => window.removeEventListener("lu:synced", load);
  }, [load]);

  const runTick = () => {
    setBusy(true); setMsg(null);
    arenaTick().then((d) => { setData(d); setMsg("本轮操盘完成。"); })
      .catch((e) => setMsg(String(e).replace(/^Error:\s*/, "")))
      .finally(() => { setBusy(false); setTimeout(() => setMsg(null), 6000); });
  };
  const reset = () => {
    if (!confirm("重置所有 AI 账户?将清空全部 AI 持仓与操盘记录。")) return;
    resetArena().then(setData).catch((e) => setMsg(String(e)));
  };

  const series: Series[] = useMemo(() => {
    if (!data) return [];
    const s: Series[] = data.agents.map((a, i) => ({
      name: a.name, color: AGENT_COLORS[i % AGENT_COLORS.length], pts: a.curve,
    }));
    if (data.benchmark.curve.length) {
      s.push({ name: data.benchmark.name, color: "#8B98A5", dashed: true, pts: data.benchmark.curve });
    }
    return s;
  }, [data]);

  const hasHistory = (data?.agents ?? []).some((a) => a.curve.length > 0);

  return (
    <>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="text-sm text-ink-dim">
          候选池 <span className="text-ink tnum">{data?.universe_size ?? 0}</span> 只(来自自选 + 持仓)
          {data?.updated_at ? <span className="text-ink-faint"> · 最近操盘 {sinceLabel(data.updated_at)}</span> : null}
        </div>
        <div className="flex items-center gap-2">
          {msg && <span className="text-xs text-ink-faint">{msg}</span>}
          <button onClick={reset} disabled={busy}
            className="rounded-lg border border-line text-ink-dim text-sm px-3 py-1.5 hover:text-ink disabled:opacity-50">重置</button>
          <button onClick={runTick} disabled={busy}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-1.5 hover:bg-accent/25 disabled:opacity-50">
            {busy ? "AI 操盘中…(约 1–2 分钟)" : "▶ 运行一轮"}
          </button>
        </div>
      </div>

      {(data?.universe_size ?? 0) === 0 && (
        <div className="rounded-lg border border-[#E0A33E]/30 bg-[#E0A33E]/10 text-[#E0A33E] text-sm px-4 py-2">
          候选池为空。请先到「自选」添加标的并点右下角「↻ 全部更新」,AI 才有可买的股票。
        </div>
      )}

      {/* 收益曲线对比 */}
      <Panel title="收益曲线对比" hint={data?.benchmark.return_pct != null ? `基准 ${data.benchmark.name} ${signedPct(data.benchmark.return_pct)}` : "% 收益 · 叠加基准"}>
        <MultiLineChart series={series} />
        <div className="flex flex-wrap gap-3 mt-2">
          {series.map((s) => (
            <span key={s.name} className="flex items-center gap-1.5 text-[11px] text-ink-dim">
              <span className="inline-block w-3 h-0.5 rounded" style={{ background: s.color, borderBottom: s.dashed ? "1px dashed" : undefined }} />
              {s.name}
            </span>
          ))}
        </div>
      </Panel>

      {/* 排行榜 */}
      <Panel title="AI 投资人排行榜" hint={`${data?.agents.length ?? 0} 位 · 同起始 ${num((data?.agents[0]?.starting_cash) ?? 100000, 0)}`}>
        {!hasHistory && (
          <p className="text-sm text-ink-faint mb-3">
            还没有操盘记录。点右上角「▶ 运行一轮」,让 4 位 AI 投资人(价值 / 成长 / 趋势 / 创新)各按风格建仓。多跑几轮即可看出谁更强。
          </p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-ink-faint border-b border-line">
                <th className="text-left font-medium py-2 w-8">#</th>
                <th className="text-left font-medium">AI 投资人</th>
                <th className="text-right font-medium">总收益</th>
                <th className="text-right font-medium">最大回撤</th>
                <th className="text-right font-medium">Sharpe</th>
                <th className="text-right font-medium">总资产</th>
                <th className="text-right font-medium">持仓</th>
                <th className="text-right font-medium w-8"></th>
              </tr>
            </thead>
            <tbody>
              {(data?.agents ?? []).map((a, i) => (
                <Row key={a.persona} a={a} color={AGENT_COLORS[i % AGENT_COLORS.length]}
                  open={open === a.persona} onToggle={() => setOpen(open === a.persona ? null : a.persona)} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-ink-faint mt-3">AI 自动操盘 · 仅为模拟与娱乐,非投资建议。数字由 LU 计算,AI 只决定买卖。</p>
      </Panel>
    </>
  );
}

function Row({ a, color, open, onToggle }: { a: ArenaAgent; color: string; open: boolean; onToggle: () => void }) {
  const ret = a.metrics.total_return_pct;
  const medal = a.rank === 1 ? "🥇" : a.rank === 2 ? "🥈" : a.rank === 3 ? "🥉" : "";
  return (
    <>
      <tr className="border-b border-line/60 hover:bg-panel-2/40 cursor-pointer" onClick={onToggle}>
        <td className="py-2.5 text-ink-dim tnum">{medal || a.rank}</td>
        <td>
          <div className="flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-full shrink-0" style={{ background: color }} />
            <div>
              <div className="font-medium text-ink">{a.name}</div>
              <div className="text-[11px] text-ink-faint">{a.tagline}</div>
            </div>
          </div>
        </td>
        <td className={`text-right tnum font-semibold ${dirClass(ret)}`}>{signedPct(ret)}</td>
        <td className="text-right tnum text-ink-dim">{a.metrics.max_drawdown_pct != null ? `-${a.metrics.max_drawdown_pct}%` : "—"}</td>
        <td className="text-right tnum text-ink-dim">{a.metrics.sharpe != null ? a.metrics.sharpe.toFixed(2) : "—"}</td>
        <td className="text-right tnum">{num(a.equity, 0)}</td>
        <td className="text-right tnum text-ink-dim">{a.positions.length}</td>
        <td className="text-right text-ink-faint">{open ? "▲" : "▼"}</td>
      </tr>
      {open && (
        <tr className="bg-base/40">
          <td colSpan={8} className="px-3 py-3">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-x-6 gap-y-1 text-xs mb-3">
              <Kv k="仓位" v={a.equity ? `${Math.round((a.invested / a.equity) * 100)}%` : "—"} />
              <Kv k="现金" v={num(a.cash, 0)} />
              <Kv k="已投入" v={num(a.invested, 0)} />
              <Kv k="年化波动" v={a.metrics.volatility_pct != null ? `${a.metrics.volatility_pct}%` : "—"} />
              <Kv k="操盘次数" v={`${a.trades_count} 笔`} />
            </div>
            {a.positions.length === 0 ? (
              <p className="text-xs text-ink-faint">本轮空仓 / 尚未建仓。</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-ink-faint border-b border-line/60">
                    <th className="text-left font-normal py-1.5">代码</th>
                    <th className="text-right font-normal">权重</th>
                    <th className="text-right font-normal">现价</th>
                    <th className="text-right font-normal">盈亏</th>
                    <th className="text-left font-normal pl-4">AI 决策理由</th>
                  </tr>
                </thead>
                <tbody>
                  {a.positions.map((p) => (
                    <tr key={p.symbol} className="border-b border-line/40 last:border-0 align-top">
                      <td className="py-1.5">
                        <Link href={`/research/${encodeURIComponent(p.symbol)}`} className="text-accent">{p.symbol}</Link>
                        {p.name ? <span className="text-ink-faint ml-1.5">{p.name}</span> : null}
                      </td>
                      <td className="text-right tnum text-ink-dim">{pct(p.weight)}</td>
                      <td className="text-right tnum text-ink-dim">{num(p.price)}</td>
                      <td className={`text-right tnum ${dirClass(p.pnl_pct)}`}>{signedPct(p.pnl_pct)}</td>
                      <td className="pl-4 text-ink-dim max-w-md">{p.last_reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function Kv({ k, v }: { k: string; v: string }) {
  return <div className="flex justify-between"><span className="text-ink-faint">{k}</span><span className="tnum text-ink-dim">{v}</span></div>;
}

/* ----------------------------------------------------------------- 我的模拟盘 (manual) */
function Manual() {
  const [acct, setAcct] = useState<PaperAccount | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ symbol: "", side: "buy" as "buy" | "sell", quantity: "" });

  const load = useCallback(() => { getPaper().then(setAcct).catch((e) => setErr(String(e))); }, []);
  useEffect(() => {
    load();
    window.addEventListener("lu:synced", load);
    return () => window.removeEventListener("lu:synced", load);
  }, [load]);

  const doTrade = () => {
    const qty = Number(form.quantity);
    if (!form.symbol.trim() || !qty || qty <= 0) return;
    setBusy(true); setErr(null);
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
    <>
      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      {acct && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Panel title="总资产"><p className="text-2xl font-semibold tnum">{num(acct.equity)}</p>
            <p className="text-xs text-ink-faint mt-1">初始 {num(acct.starting_cash, 0)}</p></Panel>
          <Panel title="现金"><p className="text-2xl font-semibold tnum">{num(acct.cash)}</p>
            <p className="text-xs text-ink-faint mt-1">已投入 {num(acct.invested)}</p></Panel>
          <Panel title="总盈亏"><p className={`text-2xl font-semibold tnum ${dirClass(acct.total_pnl)}`}>{num(acct.total_pnl)}</p>
            <p className={`text-xs mt-1 tnum ${dirClass(acct.total_return_pct)}`}>{signedPct(acct.total_return_pct)}</p></Panel>
          <Panel title="持仓数"><p className="text-2xl font-semibold tnum">{acct.positions.length}</p>
            <p className="text-xs text-ink-faint mt-1">交易 {acct.trades.length} 笔</p></Panel>
        </div>
      )}

      <Panel title="下单" hint="按缓存价成交">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Enter" && !busy) doTrade(); }}
            placeholder="代码 如 NVDA"
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
          <select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value as "buy" | "sell" })}
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent">
            <option value="buy">买入</option>
            <option value="sell">卖出</option>
          </select>
          <input value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Enter" && !busy) doTrade(); }}
            placeholder="数量" inputMode="decimal"
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
          <button onClick={doTrade} disabled={busy || !form.symbol.trim() || !Number(form.quantity)}
            className={`rounded-lg text-sm font-medium px-4 py-2 disabled:opacity-40 ${
              form.side === "buy" ? "bg-up/15 text-up hover:bg-up/25" : "bg-down/15 text-down hover:bg-down/25"
            }`}>
            {busy ? "成交中…" : form.side === "buy" ? "买入" : "卖出"}
          </button>
          <button onClick={reset}
            className="rounded-lg border border-line text-ink-dim text-sm px-4 py-2 hover:text-ink">重置账户</button>
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
                    <td className={`text-right tnum ${dirClass(p.pnl_pct)}`}>{signedPct(p.pnl_pct)}</td>
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
    </>
  );
}
