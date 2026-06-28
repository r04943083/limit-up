"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sparkline from "./Sparkline";
import ManageWatchlistModal from "./ManageWatchlistModal";
import { getWatchlists, getWatchlistQuotes, getWatchlistHealth, type Watchlist, type QuoteRow } from "@/lib/api";
import { num, signedPct, dirClass } from "@/lib/format";

// Health is a QUALITY score (not price direction), so it uses its own palette —
// brand teal = healthy, amber = neutral, gray = weak — to avoid the red/green price colors.
function healthColor(score: number): string {
  if (score >= 67) return "#21D0C3";
  if (score >= 34) return "#E0A33E";
  return "#8B98A5";
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
  groupId?: number | null; // controlled selected group (optional)
  onGroupChange?: (id: number) => void;
  onGroupsLoaded?: (groups: Watchlist[]) => void;
  onSelect?: (symbol: string) => void; // if set, row click selects in place instead of navigating
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

  const gid = groupId !== undefined ? groupId : innerGid;
  const setGid = (id: number) => {
    setInnerGid(id);
    onGroupChange?.(id);
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
      .then(setRows)
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

  return (
    <aside className="w-[300px] shrink-0 border-r border-line flex flex-col bg-base">
      {/* Group tabs + manage */}
      <div className="flex items-center gap-1 px-2 h-9 border-b border-line">
        <div className="flex items-center gap-1 overflow-x-auto flex-1 no-scrollbar">
          {groups.map((g) => (
            <button
              key={g.id}
              onClick={() => setGid(g.id)}
              className={`px-2 py-1 rounded text-xs whitespace-nowrap transition-colors ${
                g.id === gid ? "text-accent bg-panel-2" : "text-ink-dim hover:text-ink"
              }`}
              title={g.name}
            >
              {g.name}
            </button>
          ))}
        </div>
        <button
          onClick={() => setManageOpen(true)}
          className="shrink-0 text-ink-faint hover:text-accent text-xs px-1.5 py-1 rounded hover:bg-panel-2"
          title="管理自选 · 分组 / 标签 / 汇入汇出"
        >
          管理
        </button>
      </div>

      {/* Column header */}
      <div className="grid grid-cols-[1fr_auto] gap-2 px-3 h-7 items-center text-[10px] uppercase tracking-wide text-ink-faint border-b border-line/60">
        <span>名称 / 代码</span>
        <span className="text-right">最新价 · 涨跌幅</span>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {rows.length === 0 && !loading && (
          <p className="text-xs text-ink-faint p-3">此分组暂无标的。点「管理」加入或导入。</p>
        )}
        {rows.map((r) => {
          const active = activeSymbol && r.symbol.toUpperCase() === activeSymbol.toUpperCase();
          return (
            <button
              key={r.item_id}
              onClick={() => openSymbol(r.symbol)}
              className={`w-full grid grid-cols-[1fr_auto] gap-2 px-3 py-1.5 items-center border-b border-line/40 text-left transition-colors ${
                active ? "bg-panel-2" : "hover:bg-panel-2/50"
              }`}
            >
              <div className="min-w-0">
                <div className="text-[13px] text-ink truncate flex items-center gap-1.5">
                  {health[r.symbol.toUpperCase()] && (
                    <span
                      className="shrink-0 w-1.5 h-1.5 rounded-full"
                      style={{ background: healthColor(health[r.symbol.toUpperCase()].score) }}
                      title={`健康 ${Math.round(health[r.symbol.toUpperCase()].score)}/100 · ${health[r.symbol.toUpperCase()].label}`}
                    />
                  )}
                  <span className="truncate">{r.name ?? r.symbol}</span>
                </div>
                <div className="text-[11px] text-ink-faint truncate">
                  {r.symbol}
                  {r.tags && <span className="ml-1 text-ink-faint/70">· {r.tags.split(",").slice(0, 2).join(" ")}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Sparkline data={r.spark} />
                <div className="text-right w-[72px]">
                  <div className="text-[13px] tnum text-ink">{num(r.price)}</div>
                  <div className={`text-[11px] tnum ${dirClass(r.change_pct)}`}>
                    {signedPct(r.change_pct)}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <ManageWatchlistModal
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        onChanged={() => setLocalRefresh((k) => k + 1)}
        initialGid={gid}
      />
    </aside>
  );
}
