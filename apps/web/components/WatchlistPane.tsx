"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Sparkline from "./Sparkline";
import ManageWatchlistModal from "./ManageWatchlistModal";
import {
  getWatchlists, getWatchlistQuotes, getWatchlistHealth,
  moveItem, reorderItems, removeItem,
  type Watchlist, type QuoteRow,
} from "@/lib/api";
import { num, signedPct, pct, compact, dirClass } from "@/lib/format";

// Health is a QUALITY score (not price direction), so it uses its own palette —
// brand teal = healthy, amber = neutral, gray = weak — to avoid the red/green price colors.
function healthColor(score: number): string {
  if (score >= 67) return "#21D0C3";
  if (score >= 34) return "#E0A33E";
  return "#8B98A5";
}

const MARKET_LABEL: Record<string, string> = { US: "美股", HK: "港股", CN: "A股" };

// Selectable secondary metric shown per row (Futu-style customizable column, fit to a narrow pane).
type MetricKey =
  | "spark" | "change" | "turnover_rate" | "volume_ratio" | "amplitude"
  | "amount" | "market_cap" | "pct_from_high" | "pe_ttm";
const METRICS: { key: MetricKey; label: string }[] = [
  { key: "spark", label: "迷你图" },
  { key: "change", label: "涨跌额" },
  { key: "turnover_rate", label: "换手率" },
  { key: "volume_ratio", label: "量比" },
  { key: "amplitude", label: "振幅" },
  { key: "amount", label: "成交额" },
  { key: "market_cap", label: "总市值" },
  { key: "pct_from_high", label: "距52周高" },
  { key: "pe_ttm", label: "市盈率" },
];
const METRIC_LABEL = Object.fromEntries(METRICS.map((m) => [m.key, m.label])) as Record<MetricKey, string>;

type SortKey = "default" | "name" | "price" | "change_pct" | MetricKey;

function metricValue(r: QuoteRow, k: MetricKey): number | null {
  switch (k) {
    case "change": return r.change;
    case "turnover_rate": return r.turnover_rate;
    case "volume_ratio": return r.volume_ratio;
    case "amplitude": return r.amplitude;
    case "amount": return r.amount;
    case "market_cap": return r.market_cap;
    case "pct_from_high": return r.pct_from_high;
    case "pe_ttm": return r.pe_ttm;
    default: return null;
  }
}

function MetricCell({ r, k }: { r: QuoteRow; k: MetricKey }) {
  if (k === "spark") return <Sparkline data={r.spark} />;
  const v = metricValue(r, k);
  if (v == null) return <span className="text-[11px] text-ink-faint tnum">—</span>;
  if (k === "change") return <span className={`text-[11px] tnum ${dirClass(r.change)}`}>{r.change! >= 0 ? "+" : ""}{num(r.change)}</span>;
  if (k === "turnover_rate" || k === "amplitude") return <span className="text-[11px] tnum text-ink-dim">{pct(v)}</span>;
  if (k === "pct_from_high") return <span className="text-[11px] tnum text-ink-dim">{signedPct(v * 100)}</span>;
  if (k === "volume_ratio") return <span className="text-[11px] tnum text-ink-dim">{v.toFixed(2)}</span>;
  if (k === "pe_ttm") return <span className="text-[11px] tnum text-ink-dim">{v.toFixed(1)}</span>;
  return <span className="text-[11px] tnum text-ink-dim">{compact(v)}</span>; // amount / market_cap
}

export default function WatchlistPane({
  activeSymbol,
  groupId,
  onGroupChange,
  onGroupsLoaded,
  onSelect,
  refreshKey = 0,
}: {
  activeSymbol?: string;
  groupId?: number | null;
  onGroupChange?: (id: number) => void;
  onGroupsLoaded?: (groups: Watchlist[]) => void;
  onSelect?: (symbol: string) => void;
  refreshKey?: number;
}) {
  const router = useRouter();
  const [groups, setGroups] = useState<Watchlist[]>([]);
  const [innerGid, setInnerGid] = useState<number | null>(null);
  const [rows, setRows] = useState<QuoteRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [localRefresh, setLocalRefresh] = useState(0);
  const [health, setHealth] = useState<Record<string, { score: number; label: string }>>({});
  const [menuOpen, setMenuOpen] = useState(false);

  // Sort + customizable metric column (persisted).
  const [sortKey, setSortKey] = useState<SortKey>("default");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [metric, setMetric] = useState<MetricKey>("spark");
  const [metricMenu, setMetricMenu] = useState(false);
  useEffect(() => {
    try {
      const m = localStorage.getItem("lu.wl.metric") as MetricKey | null;
      if (m) setMetric(m);
      const sk = localStorage.getItem("lu.wl.sortKey") as SortKey | null;
      if (sk) setSortKey(sk);
      const sd = localStorage.getItem("lu.wl.sortDir") as "asc" | "desc" | null;
      if (sd) setSortDir(sd);
    } catch { /* no localStorage */ }
  }, []);
  const persist = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } };

  // The footer "↻ 全部更新" fires a global lu:synced after a full sync — bump localRefresh so
  // the groups/quotes/health on screen reload from the freshened cache (was a no-op before).
  useEffect(() => {
    const h = () => setLocalRefresh((v) => v + 1);
    window.addEventListener("lu:synced", h);
    return () => window.removeEventListener("lu:synced", h);
  }, []);

  // Price flash: remember the last price per symbol; flash a row when it changes.
  const prevPrice = useRef<Record<string, number>>({});
  const [flash, setFlash] = useState<Record<string, "up" | "down">>({});

  // Right-click context menu state.
  const [ctx, setCtx] = useState<{ x: number; y: number; row: QuoteRow } | null>(null);

  const stripRef = useRef<HTMLDivElement>(null);
  const drag = useRef({ down: false, startX: 0, startLeft: 0, moved: false });

  const gid = groupId !== undefined ? groupId : innerGid;
  const setGid = (id: number) => {
    setInnerGid(id);
    onGroupChange?.(id);
    requestAnimationFrame(() => {
      stripRef.current?.querySelector<HTMLElement>(`[data-gid="${id}"]`)
        ?.scrollIntoView({ inline: "center", block: "nearest" });
    });
  };

  const onStripDown = (e: React.PointerEvent) => {
    const el = stripRef.current;
    if (!el) return;
    drag.current = { down: true, startX: e.clientX, startLeft: el.scrollLeft, moved: false };
  };
  const onStripMove = (e: React.PointerEvent) => {
    const el = stripRef.current;
    if (!el || !drag.current.down) return;
    const dx = e.clientX - drag.current.startX;
    if (Math.abs(dx) > 4) drag.current.moved = true;
    el.scrollLeft = drag.current.startLeft - dx;
  };
  const endStripDrag = () => { drag.current.down = false; };
  const tabClick = (id: number) => {
    if (drag.current.moved) { drag.current.moved = false; return; }
    setGid(id);
  };

  useEffect(() => {
    getWatchlists()
      .then((gs) => {
        setGroups(gs);
        onGroupsLoaded?.(gs);
        setInnerGid((cur) => (cur && gs.some((g) => g.id === cur) ? cur : gs[0]?.id ?? null));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey, localRefresh]);

  useEffect(() => {
    if (gid == null) return;
    setLoading(true);
    getWatchlistQuotes(gid)
      .then((next) => {
        // detect price changes for the flash effect
        const f: Record<string, "up" | "down"> = {};
        for (const r of next) {
          const sym = r.symbol.toUpperCase();
          const prev = prevPrice.current[sym];
          if (prev != null && r.price != null && r.price !== prev) f[sym] = r.price > prev ? "up" : "down";
          if (r.price != null) prevPrice.current[sym] = r.price;
        }
        if (Object.keys(f).length) {
          setFlash(f);
          setTimeout(() => setFlash({}), 700);
        }
        setRows(next);
      })
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [gid, refreshKey, localRefresh]);

  useEffect(() => {
    getWatchlistHealth()
      .then((hs) => {
        const m: Record<string, { score: number; label: string }> = {};
        for (const h of hs) m[h.symbol.toUpperCase()] = { score: h.score, label: h.label };
        setHealth(m);
      })
      .catch(() => {});
  }, [refreshKey, localRefresh]);

  const openSymbol = (symbol: string) => {
    if (onSelect) onSelect(symbol);
    else router.push(`/research/${encodeURIComponent(symbol)}`);
  };

  // Sorting (nulls last). "default" keeps manual order.
  const sorted = useMemo(() => {
    if (sortKey === "default") return rows;
    const val = (r: QuoteRow): number | string | null => {
      if (sortKey === "name") return (r.name ?? r.symbol).toLowerCase();
      if (sortKey === "price") return r.price;
      if (sortKey === "change_pct") return r.change_pct;
      return metricValue(r, sortKey as MetricKey);
    };
    const dir = sortDir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = val(a); const bv = val(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" && typeof bv === "string") return av.localeCompare(bv) * dir;
      return ((av as number) - (bv as number)) * dir;
    });
  }, [rows, sortKey, sortDir]);

  const showSeparators = sortKey === "default" && new Set(rows.map((r) => r.market)).size > 1;

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) {
      const nd = sortDir === "desc" ? "asc" : "desc";
      setSortDir(nd); persist("lu.wl.sortDir", nd);
    } else {
      setSortKey(k); persist("lu.wl.sortKey", k);
      setSortDir("desc"); persist("lu.wl.sortDir", "desc");
    }
  };
  const sortArrow = (k: SortKey) => (sortKey === k ? (sortDir === "desc" ? " ↓" : " ↑") : "");

  const pickMetric = (k: MetricKey) => {
    setMetric(k); persist("lu.wl.metric", k); setMetricMenu(false);
    // if currently sorting by the old metric, follow the new one
    if (sortKey !== "default" && sortKey !== "name" && sortKey !== "price" && sortKey !== "change_pct") {
      setSortKey(k); persist("lu.wl.sortKey", k);
    }
  };

  // ── context-menu actions ──
  const doPin = async (r: QuoteRow) => {
    const ids = rows.map((x) => x.item_id);
    const next = [r.item_id, ...ids.filter((i) => i !== r.item_id)];
    setCtx(null);
    if (gid != null) { await reorderItems(gid, next).catch(() => {}); setLocalRefresh((k) => k + 1); }
  };
  const doMove = async (r: QuoteRow, targetGid: number) => {
    setCtx(null);
    await moveItem(r.item_id, targetGid).catch(() => {});
    setLocalRefresh((k) => k + 1);
  };
  const doRemove = async (r: QuoteRow) => {
    setCtx(null);
    if (!confirm(`从该分组移除 ${r.symbol}?`)) return;
    await removeItem(r.item_id).catch(() => {});
    setLocalRefresh((k) => k + 1);
  };

  let lastMarket: string | null = null;

  return (
    <aside className="w-[330px] shrink-0 border-r border-line flex flex-col bg-base">
      {/* Group tabs (drag to scroll) + dropdown-all + manage */}
      <div className="relative flex items-center gap-1 px-2 h-9 border-b border-line">
        <div
          ref={stripRef}
          onPointerDown={onStripDown}
          onPointerMove={onStripMove}
          onPointerUp={endStripDrag}
          onPointerLeave={endStripDrag}
          className="flex items-center gap-1 overflow-x-auto flex-1 no-scrollbar cursor-grab active:cursor-grabbing select-none"
        >
          {groups.map((g) => (
            <button
              key={g.id}
              data-gid={g.id}
              onClick={() => tabClick(g.id)}
              className={`px-2 py-1 rounded text-xs whitespace-nowrap transition-colors ${
                g.id === gid ? "text-accent bg-panel-2" : "text-ink-dim hover:text-ink"
              }`}
              title={g.name}
            >
              {g.name}
            </button>
          ))}
        </div>
        {groups.length > 0 && (
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className={`shrink-0 text-xs px-1 py-1 rounded hover:bg-panel-2 ${menuOpen ? "text-accent" : "text-ink-faint hover:text-ink"}`}
            title="展开全部分组"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className={`transition-transform ${menuOpen ? "rotate-180" : ""}`}>
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        )}
        <button
          onClick={() => setManageOpen(true)}
          className="shrink-0 text-ink-faint hover:text-accent text-xs px-1.5 py-1 rounded hover:bg-panel-2"
          title="管理自选 · 分组 / 标签 / 汇入汇出"
        >
          管理
        </button>

        {menuOpen && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setMenuOpen(false)} />
            <div className="absolute right-2 top-9 z-40 w-44 max-h-72 overflow-y-auto rounded-lg border border-line bg-panel shadow-2xl py-1">
              {groups.map((g) => (
                <button
                  key={g.id}
                  onClick={() => { setGid(g.id); setMenuOpen(false); }}
                  className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between hover:bg-panel-2 ${
                    g.id === gid ? "text-accent" : "text-ink-dim"
                  }`}
                >
                  <span className="truncate">{g.name}</span>
                  {g.id === gid && <span className="text-accent">✓</span>}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Column header: name (sort) | metric selector (sort) | price·change (sort) */}
      <div className="relative grid grid-cols-[1fr_auto_auto] gap-2 px-3 h-7 items-center text-[10px] uppercase tracking-wide text-ink-faint border-b border-line/60 select-none">
        <button onClick={() => toggleSort("name")} className="text-left hover:text-ink">名称/代码{sortArrow("name")}</button>
        {/* Label click = sort by this column; caret click = open the metric picker. Keeping
            them separate means opening the dropdown no longer also flips the sort direction. */}
        <div className="flex items-center gap-0.5">
          <button onClick={() => { if (metric === "spark") toggleSort("change_pct"); else toggleSort(metric); }}
            className="hover:text-ink flex items-center gap-0.5" title="按此列排序">
            {metric === "spark" ? "迷你图" : METRIC_LABEL[metric]}{sortArrow(metric === "spark" ? "change_pct" : metric)}
          </button>
          <button onClick={() => setMetricMenu((v) => !v)} className="hover:text-ink" title="选择副指标" aria-label="选择副指标">
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="m6 9 6 6 6-6" /></svg>
          </button>
        </div>
        <button onClick={() => toggleSort("price")} className="text-right hover:text-ink w-[78px]">最新·涨跌{sortArrow("price") || sortArrow("change_pct")}</button>

        {metricMenu && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setMetricMenu(false)} />
            <div className="absolute right-[78px] top-7 z-40 w-28 rounded-lg border border-line bg-panel shadow-2xl py-1">
              {METRICS.map((m) => (
                <button key={m.key} onClick={() => pickMetric(m.key)}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-panel-2 ${metric === m.key ? "text-accent" : "text-ink-dim"}`}>
                  {m.label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto" onScroll={() => ctx && setCtx(null)}>
        {sorted.length === 0 && !loading && (
          <p className="text-xs text-ink-faint p-3">此分组暂无标的。点「管理」加入或导入。</p>
        )}
        {sorted.map((r) => {
          const active = activeSymbol && r.symbol.toUpperCase() === activeSymbol.toUpperCase();
          const sym = r.symbol.toUpperCase();
          const fl = flash[sym];
          let sep: string | null = null;
          if (showSeparators && r.market !== lastMarket) { sep = MARKET_LABEL[r.market] ?? r.market; lastMarket = r.market; }
          return (
            <div key={r.item_id}>
              {sep && <div className="px-3 py-0.5 text-[10px] text-ink-faint bg-panel/40 border-b border-line/30">{sep}</div>}
              <button
                onClick={() => openSymbol(r.symbol)}
                onContextMenu={(e) => { e.preventDefault(); setCtx({ x: e.clientX, y: e.clientY, row: r }); }}
                className={`w-full grid grid-cols-[1fr_auto_auto] gap-2 px-3 py-1.5 items-center border-b border-line/40 text-left transition-colors ${
                  active ? "bg-panel-2" : "hover:bg-panel-2/50"
                } ${fl === "up" ? "flash-up" : fl === "down" ? "flash-down" : ""}`}
              >
                <div className="min-w-0">
                  <div className="text-[13px] text-ink truncate flex items-center gap-1.5">
                    {health[sym] && (
                      <span className="shrink-0 w-1.5 h-1.5 rounded-full"
                        style={{ background: healthColor(health[sym].score) }}
                        title={`健康 ${Math.round(health[sym].score)}/100 · ${health[sym].label}`} />
                    )}
                    <span className="truncate">{r.name ?? r.symbol}</span>
                  </div>
                  <div className="text-[11px] text-ink-faint truncate">
                    {r.symbol}
                    {r.tags && <span className="ml-1 text-ink-faint/70">· {r.tags.split(",").slice(0, 2).join(" ")}</span>}
                  </div>
                </div>
                <div className="flex items-center justify-end w-[60px]"><MetricCell r={r} k={metric} /></div>
                <div className="text-right w-[78px]">
                  <div className="text-[13px] tnum text-ink">{num(r.price)}</div>
                  <div className={`text-[11px] tnum ${dirClass(r.change_pct)}`}>{signedPct(r.change_pct)}</div>
                </div>
              </button>
            </div>
          );
        })}
      </div>

      {/* Right-click context menu */}
      {ctx && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setCtx(null)} onContextMenu={(e) => { e.preventDefault(); setCtx(null); }} />
          <div className="fixed z-50 w-40 rounded-lg border border-line bg-panel shadow-2xl py-1 text-xs"
            style={{ left: Math.min(ctx.x, (typeof window !== "undefined" ? window.innerWidth : 9999) - 180), top: ctx.y }}>
            <div className="px-3 py-1 text-ink-faint border-b border-line/60">{ctx.row.symbol}</div>
            <button onClick={() => doPin(ctx.row)} className="w-full text-left px-3 py-1.5 text-ink-dim hover:bg-panel-2 hover:text-ink">置顶</button>
            <div className="relative group">
              <button className="w-full text-left px-3 py-1.5 text-ink-dim hover:bg-panel-2 hover:text-ink flex items-center justify-between">
                移动到分组 <span>▸</span>
              </button>
              <div className="absolute left-full top-0 hidden group-hover:block w-36 max-h-60 overflow-y-auto rounded-lg border border-line bg-panel shadow-2xl py-1">
                {groups.filter((g) => g.id !== gid).map((g) => (
                  <button key={g.id} onClick={() => doMove(ctx.row, g.id)}
                    className="w-full text-left px-3 py-1.5 text-ink-dim hover:bg-panel-2 hover:text-ink truncate">{g.name}</button>
                ))}
                {groups.filter((g) => g.id !== gid).length === 0 && <div className="px-3 py-1.5 text-ink-faint">无其他分组</div>}
              </div>
            </div>
            <button disabled title="即将推出" className="w-full text-left px-3 py-1.5 text-ink-faint/60 cursor-not-allowed">设置提醒</button>
            <button onClick={() => doRemove(ctx.row)} className="w-full text-left px-3 py-1.5 text-down hover:bg-down/10">移除</button>
          </div>
        </>
      )}

      <ManageWatchlistModal
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        onChanged={() => setLocalRefresh((k) => k + 1)}
        initialGid={gid}
      />
    </aside>
  );
}
