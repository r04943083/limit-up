"use client";

import { useEffect, useRef, useState } from "react";
import { searchSymbols, type SymbolHit } from "@/lib/api";

/**
 * A symbol picker with autocomplete over the *downloaded* universe (ticker + name,
 * CN/EN). Use this anywhere the user types a stock code that later feeds the AI /
 * compute — it stops dirty input (typos, un-downloaded tickers, or A-share codes
 * missing the `.SS`/`.SZ` suffix) from ever reaching the backend and erroring.
 *
 * Selecting a hit writes back the *canonical* symbol (correctly suffixed). It still
 * allows free text (so paste/Enter works), but nudges users onto real symbols.
 */
const MARKET_LABEL: Record<string, string> = { US: "美股", HK: "港股", CN: "A股" };

export default function SymbolInput({
  value,
  onChange,
  onEnter,
  placeholder = "代码或名称 · 如 NVDA、0700.HK、600519",
  className = "",
  inputClassName = "w-full rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent",
  autoFocus = false,
}: {
  value: string;
  onChange: (sym: string) => void;
  onEnter?: () => void;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
  autoFocus?: boolean;
}) {
  const [hits, setHits] = useState<SymbolHit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounced autocomplete on the current text.
  useEffect(() => {
    const term = value.trim();
    if (!term) { setHits([]); return; }
    let alive = true;
    const t = setTimeout(() => {
      searchSymbols(term, 8)
        .then((r) => { if (alive) { setHits(r); setActive(0); } })
        .catch(() => { if (alive) setHits([]); });
    }, 150);
    return () => { alive = false; clearTimeout(t); };
  }, [value]);

  // Close the dropdown on outside click.
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (h: SymbolHit) => { onChange(h.symbol); setOpen(false); };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      setActive((a) => Math.min(a + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      if (open && hits[active]) { e.preventDefault(); pick(hits[active]); }
      else if (onEnter) onEnter();
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={boxRef} className={`relative ${className}`}>
      <input
        value={value}
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => { if (value.trim()) setOpen(true); }}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        autoFocus={autoFocus}
        autoComplete="off"
        spellCheck={false}
        className={inputClassName}
      />
      {open && hits.length > 0 && (
        <ul className="absolute z-40 mt-1 w-full min-w-[14rem] max-h-64 overflow-auto rounded-lg border border-line bg-panel shadow-2xl py-1">
          {hits.map((h, i) => (
            <li key={h.symbol}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => { e.preventDefault(); pick(h); }}
                className={`w-full flex items-center gap-2 px-3 py-1.5 text-left ${
                  i === active ? "bg-panel-2" : "hover:bg-panel-2/60"
                }`}
              >
                <span className="text-sm font-medium text-ink tnum w-20 shrink-0 truncate">{h.symbol}</span>
                <span className="text-xs text-ink-dim flex-1 min-w-0 truncate">{h.name ?? "—"}</span>
                {h.market && (
                  <span className="text-[10px] text-ink-faint border border-line rounded px-1 py-0.5 shrink-0">
                    {MARKET_LABEL[h.market] ?? h.market}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
