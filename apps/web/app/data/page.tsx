"use client";

import { useCallback, useEffect, useState } from "react";
import Panel from "@/components/Panel";
import { getInventory, syncAll, type Inventory } from "@/lib/api";
import { compact, sinceLabel } from "@/lib/format";

// Human-readable byte size.
function bytes(b: number | null | undefined): string {
  if (b == null) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let v = b, i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${u[i]}`;
}

function pctOf(n: number, d: number): number {
  return d > 0 ? Math.round((n / d) * 100) : 0;
}

// A labelled coverage bar (count / total + % fill). Color reflects completeness.
function Coverage({ label, n, total }: { label: string; n: number; total: number }) {
  const p = pctOf(n, total);
  const color = p >= 80 ? "#2EBD85" : p >= 40 ? "#E0A33E" : "#F6465D";
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] mb-1">
        <span className="text-ink-faint">{label}</span>
        <span className="tnum text-ink-dim">{n}/{total} · {p}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-panel-2 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${p}%`, background: color }} />
      </div>
    </div>
  );
}

export default function DataPage() {
  const [inv, setInv] = useState<Inventory | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(() => {
    getInventory().then(setInv).catch((e) => setErr(String(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  const updateAll = useCallback(async () => {
    setBusy(true);
    setNote("正在拉取最新数据到本地数据库…(自选/持仓快照 + 财报/概况 + 全局行情,并发抓取,稍候)");
    try {
      const r = await syncAll();
      const feeds = r.feeds ? Object.values(r.feeds).filter(Boolean).length : 0;
      const total = r.feeds ? Object.keys(r.feeds).length : 0;
      setNote(
        `已更新 ${r.synced}/${r.requested} 个标的快照` +
        `,财报 ${r.financials_synced ?? 0} · 概况 ${r.profiles_synced ?? 0}` +
        (total ? ` · 全局行情 ${feeds}/${total}` : "") +
        (r.failed.length ? `,失败 ${r.failed.length} 个` : "") + "。"
      );
      load();
    } catch (e) {
      setNote(`更新失败:${String(e)}`);
    } finally {
      setBusy(false);
    }
  }, [load]);

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">数据</h1>
          <p className="text-sm text-ink-dim">
            平台已下载的股票信息存量 · 美股 / A股 / 港股 · 缓存优先,无需每次联网
          </p>
        </div>
        <button onClick={updateAll} disabled={busy}
          className="shrink-0 rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-50">
          {busy ? "更新中…" : "↻ 一键更新"}
        </button>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}
      {note && <div className="rounded-lg border border-line bg-panel-2/40 text-ink-dim text-sm px-4 py-2">{note}</div>}

      {/* Totals */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Panel title="股票总数"><div className="text-2xl font-semibold tnum">{inv?.total_stocks ?? "—"}</div></Panel>
        <Panel title="K线总条数"><div className="text-2xl font-semibold tnum">{inv ? compact(inv.total_bars) : "—"}</div></Panel>
        <Panel title="研究快照"><div className="text-2xl font-semibold tnum">{inv?.total_snapshots ?? "—"}</div></Panel>
        <Panel title="数据库大小">
          <div className="text-2xl font-semibold tnum">{bytes(inv?.db_bytes)}</div>
          <div className="text-[11px] text-ink-faint mt-1">
            {inv?.last_synced_at ? `更新于 ${sinceLabel(inv.last_synced_at)}` : "未更新"}
          </div>
        </Panel>
      </div>

      {/* Per-market inventory + coverage */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {inv?.markets.map((m) => (
          <Panel key={m.market} title={m.label} hint={`${m.stocks} 只 · ${compact(m.bars)} K线`}>
            <div className="space-y-3">
              <Coverage label="日线行情" n={m.with_bars} total={m.stocks} />
              <Coverage label="研究快照(行情/基本面/新闻)" n={m.with_snapshot} total={m.stocks} />
              <Coverage label="财报三表" n={m.with_financials} total={m.stocks} />
              <Coverage label="公司概况" n={m.with_profile} total={m.stocks} />
            </div>
          </Panel>
        ))}
        {!inv && <p className="text-sm text-ink-faint">加载中…</p>}
      </div>

      <p className="text-[11px] text-ink-faint leading-relaxed">
        说明:财报与概况按需懒加载(打开个股「财报/概况」时抓取并缓存),所以覆盖率通常低于行情;
        点「一键更新」会把自选+持仓个股的财报/概况一并补齐,并刷新全局行情(指数 / A股涨停池 / 龙虎榜 / 沪深港通)。
        全市场个股的财报不会全量抓取(数量太大)。
      </p>
    </div>
  );
}
