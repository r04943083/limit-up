"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Panel from "@/components/Panel";
import {
  getUsFeeds, getUsMovers,
  type UsFeed, type MoversBoard,
} from "@/lib/api";
import { num, compact, signedPct, dirClass, errText } from "@/lib/format";

// The US analogue of the A-share 涨停 page: market-wide discovery via Yahoo movers
// (涨幅/跌幅/成交活跃/小盘急涨/高做空/低估成长). Red = up, green = down (A-share convention).
export default function DiscoverPage() {
  const router = useRouter();
  const [feeds, setFeeds] = useState<UsFeed[]>([]);
  const [kind, setKind] = useState<string>("day_gainers");
  const [board, setBoard] = useState<MoversBoard | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getUsFeeds().then(setFeeds).catch(() => setFeeds([]));
  }, []);

  const load = useCallback((k: string) => {
    setLoading(true);
    setErr(null);
    setBoard(null);
    getUsMovers(k)
      .then((r) => {
        setBoard(r.board);
        if (!r.ok) setErr(errText(r.error) || "数据源暂不可用");
      })
      .catch((e) => setErr(errText(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(kind); }, [kind, load]);

  return (
    <div className="p-5 space-y-4 overflow-auto">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-medium text-ink">发现 · 美股异动</h1>
        <span className="text-[11px] text-ink-faint">数据 Yahoo movers · 盘中刷新</span>
      </div>

      {/* Feed tabs */}
      <div className="flex flex-wrap gap-1.5">
        {feeds.map((f) => (
          <button
            key={f.kind}
            onClick={() => setKind(f.kind)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
              f.kind === kind ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink border border-line"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Panel
        title={board?.label ?? "美股异动"}
        hint={loading ? "加载中…" : err ? "数据源暂不可用" : `${board?.count ?? 0} 只 · 点标的看研究`}
      >
        {err && !board?.stocks.length ? (
          <div className="text-sm text-ink-faint py-8 text-center">{err}</div>
        ) : !board ? (
          <div className="text-sm text-ink-faint py-8 text-center">加载中…</div>
        ) : board.stocks.length === 0 ? (
          <div className="text-sm text-ink-faint py-8 text-center">暂无数据(非交易时段或数据源未提供)。</div>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-ink-faint border-b border-line">
                  <th className="text-left font-normal py-2 pr-3">代码</th>
                  <th className="text-left font-normal py-2 pr-3">名称</th>
                  <th className="text-right font-normal py-2 px-3">最新价</th>
                  <th className="text-right font-normal py-2 px-3">涨跌幅</th>
                  <th className="text-right font-normal py-2 px-3" title="成交量 / 平均量,>1 为异常放量">量比</th>
                  <th className="text-right font-normal py-2 px-3" title="距 52 周高点,0 为新高">距52周高</th>
                  <th className="text-right font-normal py-2 px-3">市值</th>
                  <th className="text-right font-normal py-2 pl-3">成交量</th>
                </tr>
              </thead>
              <tbody>
                {board.stocks.map((s) => (
                  <tr
                    key={s.symbol}
                    onClick={() => router.push(`/research/${s.symbol}`)}
                    className="border-b border-line/50 hover:bg-panel-2/60 cursor-pointer"
                  >
                    <td className="py-2 pr-3 font-medium text-accent">{s.symbol}</td>
                    <td className="py-2 pr-3 text-ink-dim max-w-[180px] truncate">{s.name ?? "—"}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{num(s.price)}</td>
                    <td className={`py-2 px-3 text-right tabular-nums ${dirClass(s.change_pct)}`}>{signedPct(s.change_pct)}</td>
                    <td className={`py-2 px-3 text-right tabular-nums ${s.vol_ratio && s.vol_ratio >= 2 ? "text-warn" : "text-ink-dim"}`}>
                      {s.vol_ratio != null ? `${s.vol_ratio.toFixed(2)}x` : "—"}
                    </td>
                    <td className={`py-2 px-3 text-right tabular-nums ${dirClass(s.from_high_pct)}`}>
                      {s.from_high_pct != null ? `${s.from_high_pct.toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums text-ink-dim">{compact(s.market_cap)}</td>
                    <td className="py-2 pl-3 text-right tabular-nums text-ink-dim">{compact(s.volume)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
