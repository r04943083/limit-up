"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import Logo from "./Logo";

type Item = { label: string; href: string; match: string; icon: ReactNode };

const I = (d: string) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {d.split("|").map((p, i) => (
      <path key={i} d={p} />
    ))}
  </svg>
);

const NAV: Item[] = [
  { label: "自选", href: "/watchlist", match: "/watchlist", icon: I("M11 3 4 9v12h14V9l-7-6Z") },
  { label: "研究", href: "/research/NVDA", match: "/research", icon: I("M4 19V5|M4 15l5-5 4 4 7-7") },
  { label: "机会", href: "/", match: "__home__", icon: I("M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0Z|M12 8v4l3 2") },
  { label: "涨停", href: "/limitup", match: "/limitup", icon: I("M12 19V5|M5 12l7-7 7 7") },
  { label: "推荐", href: "/recommendations", match: "/recommendations", icon: I("m12 3 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.8 6.8 19l1-5.8L3.5 9.2l5.9-.9L12 3Z") },
  { label: "组合", href: "/portfolio", match: "/portfolio", icon: I("M3 13a9 9 0 0 1 9-9v9h9a9 9 0 1 1-18 0Z") },
  { label: "AI用量", href: "/usage", match: "/usage", icon: I("M4 20V10|M10 20V4|M16 20v-7|M22 20H2") },
];

export default function IconRail() {
  const path = usePathname();
  return (
    <aside className="w-16 shrink-0 border-r border-line bg-panel/40 flex flex-col items-center">
      <Link href="/" title="limit-up (LU)" className="h-14 grid place-items-center w-full border-b border-line">
        <Logo size={32} className="rounded-lg" />
      </Link>
      <button
        onClick={() => window.dispatchEvent(new Event("lu:search-open"))}
        title="搜索代码  ·  ⌘K / /"
        className="w-14 mt-2 py-2 rounded-lg flex flex-col items-center gap-1 text-ink-dim hover:bg-panel-2/60 hover:text-ink transition-colors"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <span className="text-[10px] leading-none">搜索</span>
      </button>
      <nav className="flex-1 w-full py-2 flex flex-col items-center gap-1">
        {NAV.map((n) => {
          const active = n.match === "__home__" ? path === "/" : path.startsWith(n.match);
          return (
            <Link
              key={n.href}
              href={n.href}
              title={n.label}
              className={`w-14 py-2 rounded-lg flex flex-col items-center gap-1 transition-colors ${
                active ? "bg-panel-2 text-accent" : "text-ink-dim hover:bg-panel-2/60 hover:text-ink"
              }`}
            >
              {n.icon}
              <span className="text-[10px] leading-none">{n.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
