"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Global symbol search overlay (Futu-style — no full-width top bar).
 * Opens on ⌘K / Ctrl-K, on "/", or when anything dispatches `lu:search-open`
 * (the IconRail search button does). Enter → /research/<SYMBOL>.
 */
export default function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
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
    else setQ("");
  }, [open]);

  if (!open) return null;

  const go = () => {
    const s = q.trim().toUpperCase();
    if (!s) return;
    router.push(`/research/${encodeURIComponent(s)}`);
    setOpen(false);
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
            onKeyDown={(e) => e.key === "Enter" && go()}
            placeholder="搜索代码  ·  如 NVDA、0700.HK、600519.SS"
            className="flex-1 bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
          />
          <kbd className="text-[10px] text-ink-faint border border-line rounded px-1.5 py-0.5">Esc</kbd>
        </div>
        <div className="px-4 py-2 text-[11px] text-ink-faint">回车进入深度研究 · ⌘K / 「/」随处唤起</div>
      </div>
    </div>
  );
}
