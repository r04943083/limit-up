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
  { label: "机会", href: "/", match: "__home__", icon: I("M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0Z|M12 8v4l3 2") },
  { label: "自选", href: "/watchlist", match: "/watchlist", icon: I("M11 3 4 9v12h14V9l-7-6Z") },
  { label: "对话", href: "/chat", match: "/chat", icon: I("M4 5h16v11H9l-5 4V5Z") },
  { label: "推荐", href: "/recommendations", match: "/recommendations", icon: I("m12 3 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.8 6.8 19l1-5.8L3.5 9.2l5.9-.9L12 3Z") },
  { label: "选股", href: "/screener", match: "/screener", icon: I("M4 5h16l-6 7v5l-4 2v-7L4 5Z") },
  { label: "发现", href: "/discover", match: "/discover", icon: I("M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z|M15.5 8.5l-2 5-5 2 2-5 5-2Z") },
  { label: "涨停", href: "/limitup", match: "/limitup", icon: I("M12 19V5|M5 12l7-7 7 7") },
  { label: "组合", href: "/portfolio", match: "/portfolio", icon: I("M3 13a9 9 0 0 1 9-9v9h9a9 9 0 1 1-18 0Z") },
  { label: "模拟", href: "/paper", match: "/paper", icon: I("M3 7h18v10H3z|M3 11h18|M16 14h2") },
  { label: "策略", href: "/strategy", match: "/strategy", icon: I("M4 20V4|M4 20h16|M8 16l3-4 3 2 4-6") },
  { label: "复盘", href: "/replay", match: "/replay", icon: I("M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z|M10 9l5 3-5 3Z") },
  { label: "日历", href: "/calendar", match: "/calendar", icon: I("M4 5h16v15H4zM4 9h16|M8 3v4|M16 3v4") },
  { label: "日志", href: "/journal", match: "/journal", icon: I("M6 4h12v16H7a1 1 0 0 1-1-1V4Z|M9 8h6|M9 12h6") },
  { label: "AI室", href: "/studio", match: "/studio", icon: I("M12 3 2 9l10 6 10-6-10-6Z|M2 15l10 6 10-6") },
  { label: "数据", href: "/data", match: "/data", icon: I("M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Z|M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6|M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6") },
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
      <nav className="flex-1 w-full py-2 flex flex-col items-center gap-1 overflow-y-auto no-scrollbar">
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
