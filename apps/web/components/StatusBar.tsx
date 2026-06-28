"use client";

import { useEffect, useState } from "react";
import { getIndices, type IndexQuote } from "@/lib/api";
import { num, signedPct, dirClass } from "@/lib/format";
import ApiStatus from "./ApiStatus";

export default function StatusBar() {
  const [idx, setIdx] = useState<IndexQuote[]>([]);

  useEffect(() => {
    const load = () => getIndices().then(setIdx).catch(() => {});
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, []);

  return (
    <footer className="h-7 shrink-0 border-t border-line bg-panel/40 flex items-center gap-5 px-4 text-[11px] overflow-x-auto">
      {idx.map((q) => (
        <span key={q.symbol} className="flex items-center gap-1.5 whitespace-nowrap">
          <span className="text-ink-dim">{q.name}</span>
          <span className={`tnum ${dirClass(q.change_pct)}`}>{num(q.price)}</span>
          <span className={`tnum ${dirClass(q.change_pct)}`}>{signedPct(q.change_pct)}</span>
        </span>
      ))}
      <div className="ml-auto flex items-center gap-4 shrink-0">
        <ApiStatus />
        <span className="text-ink-faint whitespace-nowrap">AI 观点 · 非投资建议</span>
      </div>
    </footer>
  );
}
