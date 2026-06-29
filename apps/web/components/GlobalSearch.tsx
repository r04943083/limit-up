"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { searchSymbols, type SymbolHit } from "@/lib/api";

/**
 * Global symbol search overlay (Futu-style — no full-width top bar).
 * Opens on ⌘K / Ctrl-K, on "/", or when anything dispatches `lu:search-open`
 * (the IconRail search button does).
 *
 * It autocompletes against the *downloaded* universe (ticker + name, CN/EN) and only
 * ever opens a symbol that actually exists — so typing "tesla" no longer jumps to a
 * made-up /research/TESLA that 500s. ↑/↓ to move, Enter to open the highlighted hit.
 */
const MARKET_LABEL: Record<string, string> = { US: "美股", HK: "港股", CN: "A股" };

export default function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SymbolHit[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName || "";
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(tag);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "/" && !typing) {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("lu:search-open", onOpen as EventListener);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("lu:search-open", onOpen as EventListener);
    };
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
    else { setQ(""); setHits([]); setActive(0); }
  }, [open]);

  // Debounced autocomplete.
  useEffect(() => {
    const term = q.trim();
    if (!term) { setHits([]); setLoading(false); return; }
    setLoading(true);
    const t = setTimeout(() => {
      searchSymbols(term, 20)
        .then((rows) => { setHits(rows); setActive(0); })
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 150);
    return () => clearTimeout(t);
  }, [q]);

  if (!open) return null;

  const openSymbol = (sym: string) => {
    router.push(`/research/${encodeURIComponent(sym.toUpperCase())}`);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (hits[active]) { openSymbol(hits[active].symbol); return; }
      // Fast typist hit Enter before the debounced results arrived: resolve now and open
      // the top match (still only ever a real, downloaded symbol — never a made-up ticker).
      const term = q.trim();
      if (term) searchSymbols(term, 1).then((r) => { if (r[0]) openSymbol(r[0].symbol); });
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-start justify-center pt-[18vh]"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg mx-4 bg-panel border border-line rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-line">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" className="text-ink-faint">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="搜索代码或名称  ·  如 NVDA、Tesla、0700.HK、600519"
            className="flex-1 bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
          />
          <kbd className="text-[10px] text-ink-faint border border-line rounded px-1.5 py-0.5">Esc</kbd>
        </div>

        {q.trim() && (
          <ul className="max-h-80 overflow-auto py-1">
            {hits.map((h, i) => (
              <li key={h.symbol}>
                <button
                  onMouseEnter={() => setActive(i)}
                  onClick={() => openSymbol(h.symbol)}
                  className={`w-full flex items-center gap-3 px-4 py-2 text-left ${
                    i === active ? "bg-panel-2" : "hover:bg-panel-2/60"
                  }`}
                >
                  <span className="text-sm font-medium text-ink tnum w-24 shrink-0 truncate">{h.symbol}</span>
                  <span className="text-sm text-ink-dim flex-1 min-w-0 truncate">{h.name ?? "—"}</span>
                  {h.market && (
                    <span className="text-[10px] text-ink-faint border border-line rounded px-1.5 py-0.5 shrink-0">
                      {MARKET_LABEL[h.market] ?? h.market}
                    </span>
                  )}
                </button>
              </li>
            ))}
            {!loading && hits.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-ink-faint">
                未找到「{q.trim()}」。仅支持已下载的标的(到「数据」页查看存量)。
              </li>
            )}
            {loading && hits.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-ink-faint">搜索中…</li>
            )}
          </ul>
        )}

        <div className="px-4 py-2 text-[11px] text-ink-faint border-t border-line">
          ↑/↓ 选择 · 回车进入研究 · ⌘K / 「/」随处唤起
        </div>
      </div>
    </div>
  );
}
