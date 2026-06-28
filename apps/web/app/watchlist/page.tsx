"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import { Chip } from "@/components/ui";
import {
  getDefaultWatchlist, addItem, removeItem, importCsv, syncAll,
  type Watchlist,
} from "@/lib/api";

export default function WatchlistPage() {
  const [wl, setWl] = useState<Watchlist | null>(null);
  const [symbol, setSymbol] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reload = () => getDefaultWatchlist().then(setWl).catch((e) => setMsg(String(e)));
  useEffect(() => {
    reload();
  }, []);

  const add = async () => {
    const s = symbol.trim().toUpperCase();
    if (!s || !wl) return;
    setBusy(true);
    try {
      await addItem(wl.id, s);
      setSymbol("");
      await reload();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onFile = async (file: File) => {
    if (!wl) return;
    setBusy(true);
    try {
      const text = await file.text();
      const { added } = await importCsv(wl.id, text);
      setMsg(`Imported ${added} symbol(s).`);
      await reload();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    await removeItem(id);
    reload();
  };

  const updateAll = async () => {
    setBusy(true);
    setMsg("正在更新所有标的数据到本地数据库…");
    try {
      const r = await syncAll();
      setMsg(`已更新 ${r.synced}/${r.requested} 个标的${r.failed.length ? `,失败:${r.failed.join(", ")}` : ""}。之后页面将从数据库快速加载。`);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">{wl?.name ?? "Watchlist"}</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-ink-faint tnum">{wl?.items.length ?? 0} symbols</span>
          <button
            onClick={updateAll}
            disabled={busy}
            className="rounded-lg border border-line text-sm px-3 py-1.5 text-ink-dim hover:text-ink hover:border-accent/40 disabled:opacity-50 transition-colors"
            title="拉取最新行情/基本面/新闻并存入本地数据库,之后加载更快"
          >
            {busy ? "更新中…" : "↻ 全部更新"}
          </button>
        </div>
      </div>

      <Panel title="Add symbols" hint="US · HK · A-share">
        <div className="flex gap-2">
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="e.g. NVDA · 0700.HK · 600519.SS"
            className="flex-1 bg-base border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/60"
          />
          <button
            onClick={add}
            disabled={busy}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 hover:bg-accent/25 disabled:opacity-50"
          >
            Add
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="rounded-lg border border-line text-ink-dim text-sm px-4 hover:text-ink disabled:opacity-50"
          >
            Import CSV
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv,text/plain"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
          />
        </div>
        {msg && <p className="text-xs text-ink-faint mt-2">{msg}</p>}
      </Panel>

      <Panel title="Symbols">
        {wl && wl.items.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-ink-faint border-b border-line">
                <th className="text-left font-medium py-2">Symbol</th>
                <th className="text-left font-medium">Name</th>
                <th className="text-left font-medium">Market</th>
                <th className="text-left font-medium">Tags</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {wl.items.map((it) => (
                <tr key={it.id} className="border-b border-line/60 hover:bg-panel-2/40">
                  <td className="py-2">
                    <Link href={`/research/${encodeURIComponent(it.symbol)}`} className="text-accent font-medium">
                      {it.symbol}
                    </Link>
                  </td>
                  <td className="text-ink-dim">{it.name ?? "—"}</td>
                  <td>
                    <Chip>{it.market}</Chip>
                  </td>
                  <td className="text-ink-faint text-xs">{it.tags ?? ""}</td>
                  <td className="text-right">
                    <button onClick={() => remove(it.id)} className="text-ink-faint hover:text-down text-xs">
                      remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-ink-faint">No symbols yet. Add a ticker or import a CSV.</p>
        )}
      </Panel>
    </div>
  );
}
