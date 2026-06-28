"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV: { label: string; href: string; soon?: boolean }[] = [
  { label: "Dashboard", href: "/" },
  { label: "Watchlist", href: "/watchlist" },
  { label: "Research", href: "/research/NVDA" },
  { label: "Recommendations", href: "/recommendations", soon: true },
  { label: "Portfolio", href: "/portfolio" },
  { label: "Paper Trading", href: "/paper", soon: true },
  { label: "Journal", href: "/journal", soon: true },
  { label: "AI Coach", href: "/coach", soon: true },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-line bg-panel/40 flex flex-col">
      <div className="h-14 flex items-center gap-2 px-4 border-b border-line">
        <span className="grid place-items-center w-7 h-7 rounded-lg bg-accent/15 text-accent font-bold">
          LU
        </span>
        <span className="font-semibold tracking-tight">limit-up</span>
      </div>
      <nav className="flex-1 p-2 space-y-0.5">
        {NAV.map((n) => {
          const active = n.href === "/" ? path === "/" : path.startsWith(n.href.split("/").slice(0, 2).join("/"));
          return (
            <Link
              key={n.href}
              href={n.soon ? "#" : n.href}
              className={`w-full px-3 py-2 rounded-lg text-sm flex items-center justify-between transition-colors ${
                active ? "bg-panel-2 text-ink" : "text-ink-dim hover:bg-panel-2/60 hover:text-ink"
              } ${n.soon ? "pointer-events-none opacity-60" : ""}`}
            >
              <span>{n.label}</span>
              {n.soon && <span className="text-[10px] uppercase tracking-wide text-ink-faint">soon</span>}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 text-[11px] text-ink-faint border-t border-line">
        Not financial advice. AI output is opinion.
      </div>
    </aside>
  );
}
