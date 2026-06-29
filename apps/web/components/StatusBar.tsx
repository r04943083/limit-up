"use client";

import { useCallback, useEffect, useState } from "react";
import { getIndices, getFreshness, syncAll, type IndexQuote } from "@/lib/api";
import { num, signedPct, dirClass, sinceLabel } from "@/lib/format";
import ApiStatus from "./ApiStatus";

export default function StatusBar() {
  const [idx, setIdx] = useState<IndexQuote[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const loadIndices = useCallback(() => getIndices().then(setIdx).catch(() => {}), []);
  const loadFreshness = useCallback(
    () => getFreshness().then((rows) => setUpdatedAt(rows[0]?.synced_at ?? null)).catch(() => {}),
    [],
  );

  useEffect(() => {
    loadIndices();
    loadFreshness();
    const t = setInterval(loadIndices, 60_000);
    return () => clearInterval(t);
  }, [loadIndices, loadFreshness]);

  const updateAll = async () => {
    if (busy) return;
    setBusy(true);
    setNote(null);
    try {
      const r = await syncAll();
      setNote(`已更新 ${r.synced}/${r.requested}${r.failed.length ? ` · 失败 ${r.failed.length}` : ""}`);
      await Promise.all([loadIndices(), loadFreshness()]);
      // let any open page refresh its data now that the cache is fresh
      window.dispatchEvent(new Event("lu:synced"));
    } catch (e) {
      setNote(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
      setTimeout(() => setNote(null), 6000);
    }
  };

  return (
    <footer className="h-7 shrink-0 border-t border-line bg-panel/40 flex items-center gap-5 px-4 text-[11px] overflow-x-auto">
      {idx.map((q) => (
        <span key={q.symbol} className="flex items-center gap-1.5 whitespace-nowrap">
          <span className="text-ink-dim">{q.name}</span>
          <span className={`tnum ${dirClass(q.change_pct)}`}>{num(q.price)}</span>
          <span className={`tnum ${dirClass(q.change_pct)}`}>{signedPct(q.change_pct)}</span>
        </span>
      ))}
      <div className="ml-auto flex items-center gap-3 shrink-0">
        {note && <span className="text-ink-dim whitespace-nowrap">{note}</span>}
        <span className="text-ink-faint whitespace-nowrap">
          {updatedAt ? `更新于 ${sinceLabel(updatedAt)}` : "未更新"}
        </span>
        <button
          onClick={updateAll}
          disabled={busy}
          title="拉取全部自选 + 持仓的最新数据到本地缓存"
          className="rounded px-2 py-0.5 text-accent hover:bg-accent/15 disabled:opacity-50 whitespace-nowrap"
        >
          {busy ? "更新中…" : "↻ 全部更新"}
        </button>
        <ApiStatus />
        <span className="text-ink-faint whitespace-nowrap">AI 观点 · 非投资建议</span>
      </div>
    </footer>
  );
}
