"use client";

import { useEffect, useState } from "react";
import Panel from "@/components/Panel";
import { Stat } from "@/components/ui";
import { getUsageSummary, type UsageSummary } from "@/lib/api";
import { num, compact, sinceLabel, errText } from "@/lib/format";

const KIND_LABELS: Record<string, string> = {
  research: "个股分析", portfolio: "组合点评", recommendation: "AI 推荐",
  news: "新闻舆情", briefing: "每日简报", chat: "AI 对话",
};

export default function UsagePage() {
  const [u, setU] = useState<UsageSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getUsageSummary().then(setU).catch((e) => setErr(errText(e)));
  }, []);

  const maxTok = u ? Math.max(1, ...u.by_day.map((d) => d.total_tokens)) : 1;

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">AI 用量</h1>
        <p className="text-sm text-ink-dim">
          每次 AI 调用的 token 与成本 · 帮助你掌握 Max 套餐额度,避免用超
        </p>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      {/* Top cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Panel title="今日调用">
          <div className="text-2xl font-semibold tnum">{u?.today_calls ?? "—"}</div>
        </Panel>
        <Panel title="今日 Tokens">
          <div className="text-2xl font-semibold tnum">{u ? compact(u.today_tokens) : "—"}</div>
        </Panel>
        <Panel title="今日成本">
          <div className="text-2xl font-semibold tnum">${u ? num(u.today_cost_usd, 3) : "—"}</div>
          <div className="text-[11px] text-ink-faint mt-1">Max 套餐实际为零,此为等值估算</div>
        </Panel>
        <Panel title="累计成本">
          <div className="text-2xl font-semibold tnum">${u ? num(u.total_cost_usd, 2) : "—"}</div>
          <div className="text-[11px] text-ink-faint mt-1">
            {u ? `${u.total_calls} 次 · ${compact(u.total_tokens)} tokens` : ""}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* 14-day trend */}
        <Panel title="近 14 天 Tokens" className="lg:col-span-2">
          <div className="flex items-end gap-1 h-40">
            {u?.by_day.map((d) => (
              <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full group">
                <div
                  className="w-full rounded-t bg-accent/40 group-hover:bg-accent/70 transition-colors"
                  style={{ height: `${(d.total_tokens / maxTok) * 100}%` }}
                  title={`${d.date} · ${compact(d.total_tokens)} tokens · ${d.calls} 次`}
                />
              </div>
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-ink-faint mt-2">
            <span>{u?.by_day[0]?.date.slice(5)}</span>
            <span>{u?.by_day[u.by_day.length - 1]?.date.slice(5)}</span>
          </div>
        </Panel>

        {/* By kind */}
        <Panel title="按类型">
          {u && Object.keys(u.by_kind).length > 0 ? (
            Object.entries(u.by_kind)
              .sort((a, b) => b[1] - a[1])
              .map(([k, c]) => <Stat key={k} label={KIND_LABELS[k] ?? k} value={`${c} 次`} />)
          ) : (
            <p className="text-sm text-ink-faint">暂无调用记录。</p>
          )}
        </Panel>
      </div>

      {/* Recent calls */}
      <Panel title="最近调用">
        {u && u.recent.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-ink-faint">
                <tr className="border-b border-line">
                  <th className="text-left font-normal py-2">类型</th>
                  <th className="text-left font-normal">标的</th>
                  <th className="text-left font-normal">模型</th>
                  <th className="text-right font-normal">Tokens</th>
                  <th className="text-right font-normal">成本</th>
                  <th className="text-right font-normal">耗时</th>
                  <th className="text-right font-normal">时间</th>
                </tr>
              </thead>
              <tbody>
                {u.recent.map((c) => (
                  <tr key={c.id} className="border-b border-line/50 last:border-0">
                    <td className="py-2">{KIND_LABELS[c.kind] ?? c.kind}</td>
                    <td className="text-ink-dim">{c.symbol ?? "—"}</td>
                    <td className="text-ink-faint">{c.model?.replace("claude-", "") ?? "—"}</td>
                    <td className="text-right tnum">{compact(c.total_tokens)}</td>
                    <td className="text-right tnum">${num(c.cost_usd, 3)}</td>
                    <td className="text-right tnum text-ink-dim">{(c.duration_ms / 1000).toFixed(1)}s</td>
                    <td className="text-right text-ink-faint">{sinceLabel(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-faint">暂无调用记录。运行一次 AI 分析后这里会出现明细。</p>
        )}
      </Panel>
    </div>
  );
}
